import requests
from flask import Flask, request, redirect, session
import twilio.twiml
import keys
import re
import json
 
# The session object makes use of a secret key.
SECRET_KEY = keys.sessionKeys()
app = Flask(__name__)
app.config.from_object(__name__)

def formatQuestion(questionDict):
    questionText = questionDict.get("question", "")
    contentText = questionDict.get("content", "")
    ## !!! add in content links once they exist
    return questionText

def getQuestion(userId, count):
    headers = {"Content-Type": "application/json"}
    data=json.dumps({"count": count})
    questionRequest = requests.post(keys.askiiRoute()+'/next/'+userId, headers=headers, data=data)
    question = questionRequest.json()
    questionId = question.get("uri", None)
    if questionId:
        questionId = questionId.split("/")[-1]
    session["currentQuestion"] = questionId
    print session["currentQuestion"]
    return formatQuestion(question)

def answerQuestion(userId, questionId, answer):
    headers = {"Content-Type": "application/json"}
    data = json.dumps({"answer": str(answer)})
    url = keys.askiiRoute()+'/users/'+userId+"/"+questionId
    answerRequest = requests.post(url, headers=headers, data=data)
    ## !!! eventually check answer on API side and return 0 or 1
    print answerRequest
    # answer = answerRequest.json()
    # return answer
    return 'done'
 
@app.route("/", methods=['GET', 'POST'])
def index():
    """Respond with the number of text messages sent between two parties."""

    askiiUrl = keys.askiiRoute()
    numbers_only_regex = re.compile('^[0-9]+$')

    # session.clear()
    step = session.get('step', 0)
    counter = session.get('counter', 0)
    currentQuestion = session.get('currentQuestion', None)
 
    from_number = request.values.get('From')
    userRequest = requests.get(askiiUrl+'/users/phone_num/'+from_number)
    user = userRequest.json()["user"]
    name = user.get("name", "")
    userId = user.get("uri", None)
    if userId:
        userId = userId.split("/")[-1]

    if user == False:
        # start Welcome thread for new user
        pass

    if step == 0:
        # Ask user how much time they have
        message = "Welcome back "+name+"! How much time do you have to study today?"
        resp = twilio.twiml.Response()
        resp.sms(message)
        step += 1
        session["step"] = step
        return str(resp)

    elif step == 1:
        # check if user had a valid time response and start timer
        body = request.values.get('Body')
        is_number = numbers_only_regex.match(body)
        if not is_number:
            message = "Oops! Please enter a number in minutes. For example, if you have 10 minutes to study, please enter 10."
            resp = twilio.twiml.Response()
            resp.sms(message)
            return str(resp)
        else:
            message = getQuestion(userId, counter)
            resp = twilio.twiml.Response()
            resp.sms(message)
            step += 1
            counter += 1
            session["step"] = step
            session["counter"] = counter
            return str(resp)

    else:
        # answer first, then get next question
        if currentQuestion:
            answer = answerQuestion(userId, currentQuestion, 0)
        message = getQuestion(userId, counter)
        resp = twilio.twiml.Response()
        resp.sms(message)
        counter += 1
        session["counter"] = counter
        return str(resp)

    return str('done')

 
if __name__ == "__main__":
    app.run(debug=True)