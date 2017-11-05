# Test file, used to test making calls

from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

# Your Account SID from twilio.com/console
account_sid = "ACa7e27f592a57a9ec9d23873331ddbdad"
# Your Auth Token from twilio.com/console
auth_token  = "1b77f5e9dc4db4f0d8655a38c1924f23"

client = Client(account_sid, auth_token)

call = client.calls.create(
    to="+19788579570",
    from_="+18573203552",
    url="https://handler.twilio.com/twiml/EH79b471e1be5b4f670b818845bf13a026?Name=Christina?AppointmentDay=Saturday?AppointmentType=Cardiologist")

print(call.sid)
