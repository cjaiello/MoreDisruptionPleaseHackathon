import os
import smtplib
import psycopg2
import re
from time import localtime, strftime
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, request, Response, jsonify, render_template
from wtforms import Form, TextField, TextAreaField, validators, StringField, SubmitField

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ['DATABASE_URL']
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
DB = SQLAlchemy(app)
SCHEDULER = BackgroundScheduler()


# Create our database model
class Patient(DB.Model):
    __tablename__ = "patients"
    id = DB.Column(DB.Integer, primary_key=True)
    patient_id = DB.Column(DB.String(120), unique=True)
    patient_password = DB.Column(DB.String(120))
    reminder_hour = DB.Column(DB.Integer)
    reminder_minute = DB.Column(DB.Integer)
    patient_contact_phone_number = DB.Column(DB.String(120))
    patient_phone_number = DB.Column(DB.String(120))
    patient_contact_name = DB.Column(DB.String(120))

    def __init__(self, patient_id, patient_password, reminder_hour, reminder_minute, patient_contact_phone_number, patient_phone_number, patient_contact_name):
        self.patient_id = patient_id
        self.patient_password = patient_password
        self.reminder_hour = reminder_hour
        self.reminder_minute = reminder_minute
        self.patient_contact_phone_number = patient_contact_phone_number
        self.patient_phone_number = patient_phone_number
        self.patient_contact_name = patient_contact_name

    def __repr__(self):
        return '<Patient %r>' % self.patient_id


# Our form model
class PatientForm(Form):
    patient_id = TextField('Username:', validators=[validators.required()])
    patient_password = TextField('Password:')
    reminder_hour = TextField('Time to Call Patient:')
    reminder_minute = TextField('Time to Call Patient:')
    patient_phone_number = TextField('Patient\'s Phone Number:')
    patient_contact_name = TextField('Patient Contact\'s Name:')
    patient_contact_phone_number = TextField('Patient Contact\'s Phone Number:')


@app.route("/", methods=['GET', 'POST'])
def homepage():
    form = PatientForm(request.form)

    if request.method == 'POST':
        # Get form input
        patient_id = request.form['patient_id']
        patient_password = request.form['patient_password']
        reminder_hour = remove_starting_zeros_from_time(request.form['reminder_hour'])
        reminder_minute = remove_starting_zeros_from_time(request.form['reminder_minute'])
        patient_phone_number = parse_phone_number(request.form['patient_phone_number'])
        patient_contact_name = parse_phone_number(request.form['patient_contact_name'])
        patient_contact_phone_number = parse_phone_number(request.form['patient_contact_phone_number'])
        # If the form field was valid...
        if form.validate():
            # Look for patient in database
            if not DB.session.query(Patient).filter(Patient.patient_id == patient_id).count():
                # Patient isn't in database. Create our patient object and add them to the database
                patient = Patient(patient_id, reminder_hour, reminder_minute, patient_contact_phone_number, patient_phone_number, patient_contact_name)
                DB.session.add(patient)
                DB.session.commit()
                # Adding this additional phone call job to the queue
                SCHEDULER.add_job(trigger_phone_call, 'cron', [patient_form.patient_id, patient_phone_number], day_of_week='sun-sat', hour=reminder_hour, minute=reminder_minute, id=patient_form.patient_id + "_patient_call")
                print(create_logging_label() + "Set " + patient_id + "'s reminder time to " + str(reminder_hour) + ":" + format_minutes_to_have_zero(reminder_minute) + " with reminder patient_contact_phone_number: " + patient_phone_number)

            else:
                # Update user's info (if values weren't empty)
                patient = Patient.query.filter_by(patient_id = patient_id).first()
                patient.reminder_hour = reminder_hour if reminder_hour != None else patient_form.reminder_hour
                patient.reminder_minute = reminder_minute if reminder_minute != None else patient_form.reminder_minute
                patient.patient_contact_phone_number = patient_contact_phone_number if patient_contact_phone_number != None else patient_contact_phone_number
                patient.patient_contact_name = patient_contact_name if patient_contact_name != None else patient_contact_name
                patient.patient_phone_number = patient_phone_number if patient_phone_number != None else patient.patient_phone_number
                DB.session.commit()
                # Next we will update the call the patient job if one of those values was edited
                if (patient_phone_number != None or reminder_hour != None or reminder_minute != None):
                    # Updating this job's timing (need to delete and re-add)
                    SCHEDULER.remove_job(patient_id + "_patient_call")
                    SCHEDULER.add_job(trigger_phone_call, 'cron', [patient_form.patient_id, patient_form.patient_phone_number], day_of_week='sun-sat', hour=patient_form.reminder_hour, minute=patient_form.reminder_minute, id=patient_form.patient_id + "_patient_call")
                    print(create_logging_label() + "Updated " + patient_id + "'s call time to " + str(patient_form.reminder_hour) + ":" + format_minutes_to_have_zero(patient_form.reminder_minute) + " with phone number patient_contact_phone_number: " + patient_phone_number)
        else:
            print(create_logging_label() + "Could not update reminder time. Issue was: " + str(request))

    return render_template('homepage.html', form=form)


# Setting the reminder schedules for already-existing jobs
# @return nothing
def set_schedules():
    print(create_logging_label() + "Loading previously-submitted reminder data.")
    # Get all rows from our table
    patients_with_scheduled_reminders = Patient.query.all()
    # Loop through our results
    for patient in patients_with_scheduled_reminders:
        # Add a job for each row in the table, sending reminder patient_contact_phone_number to channel
        SCHEDULER.add_job(trigger_phone_call, 'cron', [patient.patient_id, patient.patient_phone_number], day_of_week='sun-sat', hour=patient.reminder_hour, minute=patient.reminder_minute, id=patient.patient_id + "_patient_call")
        print(create_logging_label() + "Patient name and time that we scheduled call for: " + patient.patient_id + " at " + str(patient.reminder_hour) + ":" + format_minutes_to_have_zero(patient.reminder_minute) + " with patient_contact_phone_number: " + patient.patient_phone_number)


# Function that triggers the reminder call
# Here is where we need to add in the Google Voice API to make calls
# We also need to store responses in our database
def trigger_phone_call(patient_id, phone_number):
    return null;


# Will fetch the patient's response from database
def get_patient_responses(patient_id):
    return null


# ------ Util Functions ------ #


# Used for logging when actions happen
# @return string with logging time
def create_logging_label():
    return strftime("%Y-%m-%d %H:%M:%S", localtime()) + "| "


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


# Scheduler doesn't like zeros at the start of numbers...
# @param time: string to remove starting zeros from
def remove_starting_zeros_from_time(time):
    return (re.search( r'0?(\d+)?', time, re.M|re.I)).group(1)


if __name__ == '__main__':
    app.run(host='0.0.0.0')

# Setting the scheduling
set_schedules()

# Running the scheduling
SCHEDULER.start()

print(create_logging_label() + "Patient Call Bot was started up and scheduled.")
