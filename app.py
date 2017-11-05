import os
import smtplib
import psycopg2
import re
from time import localtime, strftime
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, Response, jsonify, render_template
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse
import time


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
DB = SQLAlchemy(app)
SCHEDULER = BackgroundScheduler()
ACCOUNT_SID = "ACa7e27f592a57a9ec9d23873331ddbdad"
AUTH_TOKEN  = "1b77f5e9dc4db4f0d8655a38c1924f23"
CLIENT = Client(ACCOUNT_SID, AUTH_TOKEN)


# Create our database model
class Patient(DB.Model):
    __tablename__ = "patients"
    id = DB.Column(DB.Integer, primary_key=True)
    patient_id = DB.Column(DB.String(120), unique=False)
    reminder_hour = DB.Column(DB.Integer)
    reminder_minute = DB.Column(DB.Integer)
    patient_contact_phone_number = DB.Column(DB.String(120), unique=False)
    patient_phone_number = DB.Column(DB.String(120), unique=False)
    patient_contact_name = DB.Column(DB.String(120), unique=False)
    patient_name = DB.Column(DB.String(120), unique=False)

    def __init__(self, patient_id, reminder_hour, reminder_minute, patient_contact_phone_number, patient_phone_number, patient_contact_name, patient_name):
        self.id = int(patient_id)
        self.patient_id = patient_id
        self.reminder_hour = reminder_hour
        self.reminder_minute = reminder_minute
        self.patient_contact_phone_number = patient_contact_phone_number
        self.patient_phone_number = patient_phone_number
        self.patient_contact_name = patient_contact_name
        self.patient_name = patient_name

    def __repr__(self):
        return '<Patient %r>' % self.patient_id


# Our form model
class PatientForm(Form):
    patient_id = TextField('Patient ID:', validators=[validators.required()])
    reminder_hour = TextField('Time to Call Patient:')
    reminder_minute = TextField('Time to Call Patient:')
    patient_phone_number = TextField('Patient\'s Phone Number:')
    patient_contact_name = TextField('Patient Contact\'s Name:')
    patient_contact_phone_number = TextField('Patient Contact\'s Phone Number:')
    am_or_pm = ['am', 'pm']
    patient_name = TextField('Patient Name:')


@app.route("/", methods=['GET', 'POST'])
def homepage():
    form = PatientForm(request.form)

    if request.method == 'POST':
        # Get form input
        patient_id = request.form['patient_id']
        patient_name = request.form['patient_name']
        reminder_hour = remove_starting_zeros_from_time(request.form['reminder_hour'])
        reminder_minute = remove_starting_zeros_from_time(request.form['reminder_minute'])
        patient_phone_number = parse_phone_number(request.form['patient_phone_number'])
        patient_contact_name = parse_phone_number(request.form['patient_contact_name'])
        patient_contact_phone_number = parse_phone_number(request.form['patient_contact_phone_number'])
        am_or_pm = parse_phone_number(request.form['am_or_pm'])
        # If the form field was valid...
        if form.validate():
            # Look for patient in database
            if not DB.session.query(Patient).filter(Patient.patient_id == patient_id).count():
                # Patient isn't in database. Create our patient object and add them to the database
                patient = Patient(patient_id, calculate_am_or_pm(reminder_hour, am_or_pm), reminder_minute, (patient_contact_phone_number).strip(), (patient_phone_number).strip(), (patient_contact_name).strip(), (patient_name).strip())
                DB.session.add(patient)
                DB.session.commit()
                # Adding this additional phone call job to the queue
                log("ID: " + str(patient_id) + "Phone: " + str(patient_phone_number) + "Name: " + str(patient_name) + "Hour: " + str(int(calculate_am_or_pm(reminder_hour, am_or_pm))) + "Minute: " + str(reminder_minute) + "Job ID: " + str(patient.patient_id))
                SCHEDULER.add_job(trigger_checkup_call, 'cron', [patient_id, patient_phone_number, patient_name], hour=int(calculate_am_or_pm(reminder_hour, am_or_pm)), minute=reminder_minute, id=patient.patient_id)
                log("Job ID is: " + patient.patient_id)
                log("Set " + patient_id + "'s reminder time to " + str(reminder_hour) + ":" + format_minutes_to_have_zero(reminder_minute) + " " + am_or_pm + " with reminder patient_phone_number: " + patient_phone_number)

            else:
                # Update user's info (if values weren't empty)
                patient = Patient.query.filter_by(patient_id = patient_id).first()
                patient.reminder_hour = reminder_hour if reminder_hour != None else patient.reminder_hour
                patient.reminder_minute = reminder_minute if reminder_minute != None else patient.reminder_minute
                patient.patient_contact_phone_number = patient_contact_phone_number if patient_contact_phone_number != None else patient_contact_phone_number
                patient.patient_contact_name = patient_contact_name if patient_contact_name != None else patient_contact_name
                patient.patient_phone_number = patient_phone_number if patient_phone_number != None else patient.patient_phone_number
                patient.patient_name = patient_name if patient_name != None else patient.patient_name
                patient.reminder_hour = calculate_am_or_pm(reminder_hour, am_or_pm)
                DB.session.commit()
                # Next we will update the call the patient job if one of those values was edited
                if (patient_phone_number != None or reminder_hour != None or reminder_minute != None):
                    # Updating this job's timing (need to delete and re-add)
                    SCHEDULER.remove_job(patient_id)
                    SCHEDULER.add_job(trigger_checkup_call, 'cron', [patient.patient_id, patient.patient_phone_number, patient.patient_name], hour=int(calculate_am_or_pm(reminder_hour, am_or_pm)), minute=patient.reminder_minute, id=patient.patient_id)
                    log("Updated " + patient_id + "'s call time to " + str(patient.reminder_hour) + ":" + format_minutes_to_have_zero(patient.reminder_minute) + " " + am_or_pm + " with phone number patient_phone_number: " + patient.patient_phone_number)
        else:
            log("Could not update reminder time. Issue was: " + str(request))

    return render_template('homepage.html', form=form)


@app.route("/test", methods=['GET', 'POST'])
def testpage():
    call = CLIENT.calls.create(
        to="+1" + request.args.get('number'),
        from_="+18573203552",
        url="https://handler.twilio.com/twiml/EH3b9b39d5bc1a6958a8945ee8b4a9863a?Name=Christina")
    return render_template('testpage.html')


# Setting the reminder schedules for already-existing jobs
# @return nothing
def set_schedules():
    log("Loading previously-submitted call data.")
    # Get all rows from our table
    patients_with_scheduled_reminders = Patient.query.all()
    # Loop through our results
    for patient in patients_with_scheduled_reminders:
        log("Patient Being Added or Updated: " + patient.patient_name)
        # Add a job for each row in the table, sending reminder patient_contact_phone_number to channel
        SCHEDULER.add_job(trigger_checkup_call, 'cron', [patient.patient_id, patient.patient_phone_number, patient.patient_name], hour=patient.reminder_hour, minute=patient.reminder_minute, id=patient.patient_id + "_patient_call")
        log("Patient name and time that we scheduled call for: " + patient.patient_name + " at " + str(patient.reminder_hour) + ":" + format_minutes_to_have_zero(patient.reminder_minute) + " with patient_contact_phone_number: " + patient.patient_phone_number)


# Function that triggers the wellness call
# Here is where we need to add in the Google Voice API to make calls
# We also need to store responses in our database
def trigger_checkup_call(patient_id, phone_number, patient_name):
    log("Calling patient with ID " + patient_id + " and name " + patient_name + " at phone number " + phone_number)
    call = CLIENT.calls.create(
    to="+" + phone_number,
    from_="+18573203552",
    url="https://handler.twilio.com/twiml/EH3b9b39d5bc1a6958a8945ee8b4a9863a?" + str(patient_name).strip())


# Function that triggers a followup call after an appointment
def trigger_followup_call(patient_id, phone_number, patient_name, appointment_day, appointment_type):
    log("Calling patient with ID " + patient_id + " and name " + patient_name + " at phone number " + phone_number)
    call = CLIENT.calls.create(
    to="+" + phone_number,
    from_="+18573203552",
    url="https://handler.twilio.com/twiml/EH79b471e1be5b4f670b818845bf13a026?Name=" + str(patient_name).strip() + "&AppointmentDay=" + appointment_day.strip() + "&AppointmentType=" + appointment_type.strip())


# Makes a call to someone
def placeEmergencyCall(patient_name, phone_number, patient_contact_name, symptom):
    url = ""
    if (symptom != None):
        url = "https://handler.twilio.com/twiml/EH9fb208ad494c53c3e252fdf11782db85?Name=" + patient_name.strip() + "&ContactName=" + patient_contact_name.strip() + "&Symptom=" + symptom
        log("Placing a call to " + patient_name + "'s contact " + patient_contact_name + " at number " + phone_number + " with symptom " + str(symptom))
    else:
        url = "https://handler.twilio.com/twiml/EH5902f7e1b80f2e83c38860c373ead6b9?Name=" + patient_name.strip() + "&ContactName=" + patient_contact_name.strip()
        log("Placing a call to " + patient_name + "'s contact " + patient_contact_name + " at number " + phone_number)
    call = CLIENT.calls.create(
    to="+1" + phone_number,
    from_="+18573203552",
    url=url)


# Calls for help
@app.route("/help", methods=['GET', 'POST'])
def help():
    # Get the patient's phone number out of the query string
    patient_phone_number = request.args.get('Called')
    log("Patient in need of help is: " + patient_phone_number)
    # Grab that patient from the database
    patient = Patient.query.filter_by(patient_phone_number = patient_phone_number).first()
    log("Emergency contact to call is: " + patient.patient_contact_phone_number)
    # Call their emergency contact
    placeEmergencyCall(patient.patient_name, patient.patient_contact_phone_number, patient.patient_contact_name)


# This should store the user's response recording URLs somewhere,
# or it can get the user's transcriptions
@app.route("/recording", methods=['GET', 'POST'])
def recording():
    log("A call was made. Information: " + str(request))
    return(str(request))


# Test method
@app.route("/transcribe", methods=['GET', 'POST'])
def transcribe():
    request_values = request.values
    log("Transcription Request Values: " + str(request_values))
    # This is the number of the patient whom we just called:
    patient_phone_number = request_values.get("To")
    log("Phone number of patient whose message we transcribed: " + patient_phone_number)
    transcription_status = request_values.get("TranscriptionStatus")
    log("Transcription Status: " + transcription_status)
    if (transcription_status != "failed"):
        # This is what the patient said:
        transcription_text = request_values.get("TranscriptionText")
        log("Transcription Text: " + transcription_text)
        symptoms = ["pain", "sick", "bad", "nausea", "nauseous", "dizzy", "ill", "unwell", "help"]
        for symptom in symptoms:
            if (symptom in transcription_text):
                patient = Patient.query.filter_by(patient_phone_number = patient_phone_number.replace("+1","")).first()
                log("Placing a call to " + patient.patient_name + "'s emergency contact " + patient.patient_contact_name + " at " + patient.patient_contact_phone_number + " due to symptom " + symptom)
                placeEmergencyCall(patient.patient_name, patient.patient_contact_phone_number, patient.patient_contact_name, symptom)
    log(str(request_values))
    return(str(request_values))


# Will fetch the patient's response from database
def get_patient_responses(patient_id):
    return null


# ------ Util Functions ------ #


# Scheduler doesn't like zeros at the start of numbers...
# @param time: string to remove starting zeros from
def remove_starting_zeros_from_time(time):
    return (re.search( r'0?(\d+)?', time, re.M|re.I)).group(1)


# Creates a log message
def log(logged_text):
    print(strftime("%Y-%m-%d %H:%M:%S", localtime()) + "| " + logged_text)


# For logging purposes
def format_minutes_to_have_zero(minutes):
    if minutes == None:
        return "00"
    else:
        if(int(minutes) < 10):
            return "0" + str(minutes)
        else:
            return str(minutes)


# Parse phone number
def parse_phone_number(phone_number_string):
    # Remove dashes
    phone_number_string = phone_number_string.replace('-','')
    # Remove spaces
    phone_number_string = phone_number_string.replace(' ','')
    # Remove parens
    phone_number_string = phone_number_string.replace('(','')
    phone_number_string = phone_number_string.replace(')','')
    #Remove periods
    phone_number_string = phone_number_string.replace('.','')
    return phone_number_string


# Adds 12 if PM else keeps as original time
def calculate_am_or_pm(reminder_hour, am_or_pm):
    if (am_or_pm == "pm"):
        reminder_hour  = int(reminder_hour) + 12
    return reminder_hour


if __name__ == '__main__':
    app.run(host='0.0.0.0')

# Setting the scheduling
set_schedules()

# Running the scheduling
SCHEDULER.start()

log("Patient Call Bot was started up and scheduled.")
