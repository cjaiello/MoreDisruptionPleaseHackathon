from flask import Flask
from twilio.twiml.voice_response import VoiceResponse

app = Flask(__name__)

@app.route("/", methods=['GET', 'POST'])
def hello_monkey():
    """Respond to incoming requests."""
    resp = VoiceResponse()
    resp.say("Hello Monkey")

    return str(resp)

if __name__ == "__main__":
    app.run(debug=True)
