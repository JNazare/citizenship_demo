import requests
from flask import Flask, request, redirect, session
import twilio.twiml
import keys
import re
import json
import time
 
# The session object makes use of a secret key.
SECRET_KEY = keys.sessionKeys()
app = Flask(__name__)
app.config.from_object(__name__)

def formatQuestion(questionDict):
    questionText = questionDict.get("question", "")
    contentText = questionDict.get("content", "")
    ## !!! add in content links once they exist
    return questionText

def getIdFromUri(uri):
    if uri:
        return uri.split("/")[-1]
    return None

def getQuestion(userId, count):
    headers = {"Content-Type": "application/json"}
    data=json.dumps({"count": count})
    questionRequest = requests.post(keys.askiiRoute()+'/next/'+userId, headers=headers, data=data)
    question = questionRequest.json()
    questionId = getIdFromUri(question.get("uri", None))
    session["currentQuestion"] = questionId
    return formatQuestion(question)

def answerQuestion(userId, questionId, answer):
    headers = {"Content-Type": "application/json"}
    data = json.dumps({"answer": str(answer)})
    url = keys.askiiRoute()+'/users/'+userId+"/"+questionId
    answerRequest = requests.post(url, headers=headers, data=data)
    ## !!! eventually check answer on API side and return 0 or 1
    return 'done'

def outOfTime():
    session["startTime"] = session.get('startTime', None)
    session["studyDuration"] = session.get('studyDuration', None)
    if session["startTime"] and session["studyDuration"]:
        if time.time() - session["startTime"] > (session["studyDuration"])*60:
            return True
    return False

def lookupUser(phone_num):
    askiiUrl = keys.askiiRoute()
    userRequest = requests.get(askiiUrl+'/users/phone_num/'+phone_num)
    user = userRequest.json()["user"]
    name = user.get("name", "")
    userId = getIdFromUri(user.get("uri", None))
    session["userId"] = userId
    return user

def endSession():
    message = "Nice work! You've studied for "+ str(session["studyDuration"]) + "! Come back and study soon."
    session.clear()
    return message

def timeoutSession():
    if time.time() - session["prevTime"] > 2*60:
        if not session["startTime"] and not session["studyDuration"]:
            session.clear()
            session["step"] = 0
    return 

@app.route("/", methods=['GET', 'POST'])
def index():
    """Respond with the number of text messages sent between two parties."""

    # session.clear()
    askiiUrl = keys.askiiRoute()
    numbers_only_regex = re.compile('^[0-9]+$')

    # get all session fields
    session["step"] = session.get('step', 0)
    session["counter"] = session.get('counter', 0)
    session["currentQuestion"] = session.get('currentQuestion', None)
    session["startTime"] = session.get('startTime', None)
    session["studyDuration"] = session.get('studyDuration', None)
    session["userId"] = session.get('userId', None)
    session["prevTime"] = session.get('prevTime', time.time())

    if outOfTime() == True:
        if session.get('currentQuestion', None):
            answer = answerQuestion(session["userId"], session["currentQuestion"], 0)
        message = endSession()
        resp = twilio.twiml.Response()
        resp.sms(message)
        return str(resp)
    
    else:
        # lookup user
        phone_num = request.values.get('From')
        user = lookupUser(phone_num)

        # if no user
        if user == False:
            # start welcome messages to get user name
            pass
        else:
            timeoutSession()
            if session.get("step", 0) == 0:
                # Ask user how much time they have
                message = "Welcome back "+user.get("name", "")+"! How much time do you have to study today?"
                resp = twilio.twiml.Response()
                resp.sms(message)
                session["step"] += 1
                session["prevTime"] = time.time()
                return str(resp)
            elif session.get("step", 0) == 1:
                # timer is getting stuck here
                studyDuration = request.values.get('Body')
                is_number = numbers_only_regex.match(studyDuration)
                if not is_number:
                    message = "Oops! Please enter a number in minutes. For example, if you have 10 minutes to study, please enter 10."
                    resp = twilio.twiml.Response()
                    resp.sms(message)
                    session["prevTime"] = time.time()
                    return str(resp)
                else:
                    message = getQuestion(session["userId"], session["counter"])
                    resp = twilio.twiml.Response()
                    resp.sms(message)
                    session["step"] += 1
                    session["counter"] += 1
                    session["startTime"] = time.time()
                    session["studyDuration"] = int(studyDuration)
                    return str(resp)
            elif session.get("step", 0) > 1:
                if session["currentQuestion"]:
                    answer = answerQuestion(session["userId"], session["currentQuestion"], 0)
                message = getQuestion(session["userId"], session["counter"])
                resp = twilio.twiml.Response()
                resp.sms(message)
                session["counter"] += 1
                return str(resp)
    
    return str('done')

    # if session["startTime"] and session["studyDuration"]:
    #     if time.time() - session["startTime"] > (session["studyDuration"]+2)*60:
    #         session["step"] = 0
    #         session["counter"] = 0
    #         session["startTime"] = None
    #         session["studyDuration"] = None

    # if user == False:
    #     # start Welcome thread for new user
    #     pass

    # if step == 0:
    #     # Ask user how much time they have
    #     message = "Welcome back "+name+"! How much time do you have to study today?"
    #     resp = twilio.twiml.Response()
    #     resp.sms(message)
    #     step += 1
    #     session["step"] = step
    #     return str(resp)

    # elif step == 1:
    #     # check if user had a valid time response and start timer
    #     # timer is getting stuck here
    #     studyDuration = request.values.get('Body')
    #     is_number = numbers_only_regex.match(studyDuration)
    #     if not is_number:
    #         message = "Oops! Please enter a number in minutes. For example, if you have 10 minutes to study, please enter 10."
    #         resp = twilio.twiml.Response()
    #         resp.sms(message)
    #         return str(resp)
    #     else:
    #         message = getQuestion(userId, counter)
    #         resp = twilio.twiml.Response()
    #         resp.sms(message)
    #         step += 1
    #         counter += 1
    #         session["step"] = step
    #         session["counter"] = counter
    #         session["startTime"] = time.time()
    #         session["studyDuration"] = int(studyDuration)
    #         return str(resp)

    # elif step > 1:
    #     # answer first, then get next question
    #     # JULES check that these times exist!! >> if startTime and studyDuration:
    #     if session["startTime"] and session["studyDuration"]:
    #         if time.time() - session["startTime"] < session["studyDuration"]*60:
    #             if currentQuestion:
    #                 answer = answerQuestion(userId, currentQuestion, 0)
    #             message = getQuestion(userId, counter)
    #             resp = twilio.twiml.Response()
    #             resp.sms(message)
    #             counter += 1
    #             session["counter"] = counter
    #             return str(resp)

    #     if session["startTime"] and session["studyDuration"]:
    #         if time.time() - session["startTime"] >= session["studyDuration"]*60:
    #             message = "Nice work! You've studied for "+ str(studyDuration) + "! Come back and study soon."
    #             resp = twilio.twiml.Response()
    #             resp.sms(message)
    #             session["step"] = 0
    #             session["counter"] = 0
    #             session["startTime"] = None
    #             session["studyDuration"] = None
    #             return str(resp)

    # return str('done')

 
if __name__ == "__main__":
    app.run(debug=True)