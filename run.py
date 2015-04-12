import requests
from flask import Flask, request, redirect, session
import twilio.twiml
import keys
import re
import json
import time
import os
 
# The session object makes use of a secret key.
SECRET_KEY = keys.sessionKeys()
app = Flask(__name__)
app.config.from_object(__name__)
askiiUrl = keys.askiiRoute()
key = keys.askiiKey()
headers = {"Content-Type": "application/json"}

def formatQuestion(questionDict):
    questionText = questionDict.get("question", "")
    infoUri = questionDict.get("info_uri", "")+"?key="+key
    message = questionText + "\n\nYou can find the answer here: " + infoUri
    return message

def formatHint(questionId):
    questionRequest = requests.get(askiiUrl+'/questions/'+questionId+"?key="+key)
    question = questionRequest.json()["question"]
    hint = question.get("hint", "")
    message = "Sorry, that's incorrect. Here's a hint: " + hint
    return message

def formatInfoHint(questionId):
    questionRequest = requests.get(askiiUrl+'/questions/'+questionId+"?key="+key)
    question = questionRequest.json()["question"]
    infoUri = question.get("info_uri", "")
    message = "Sorry, that's still incorrect. I'd reccomend looking at the information on the link one more time: " + infoUri
    return message

def getIdFromUri(uri):
    if uri:
        return uri.split("/")[-1]
    return None

def incorrentAndGetQuestion(userId, count):
    newQuestionMessage = getQuestion(userId, count)
    message = "Sorry, that is incorrect. We will come back to this question soon. Let's look at another question.\n\n"+newQuestionMessage
    return message

def correctAndGetQuestion(userId, count):
    newQuestionMessage = getQuestion(userId, count)
    message = "Correct! Next question.\n\n"+newQuestionMessage
    return message

def getQuestion(userId, count):
    data=json.dumps({"count": count})
    questionRequest = requests.post(askiiUrl+'/next/'+userId+"?key="+key, headers=headers, data=data)
    question = questionRequest.json()
    questionId = getIdFromUri(question.get("uri", None))
    session["currentQuestion"] = questionId
    return formatQuestion(question)

def checkRegex(regex_str, answer):
    regex_obj = re.compile(regex_str, re.IGNORECASE)
    answer = str(answer).strip().lower()
    if regex_obj.search(answer) != None:
        return 1
    return 0

def answerQuestion(userId, questionId, answer):
    questionJson = requests.get(askiiUrl+'/questions/'+questionId+"?key="+key, headers=headers).json()["question"]
    num_answer = checkRegex(questionJson["regex"], str(answer))
    bool_answer = True if num_answer == 1 else False
    data = json.dumps({"answer": str(num_answer)})
    url = askiiUrl+'/users/'+userId+"/"+questionId+"?key="+key
    answerRequest = requests.post(url, headers=headers, data=data)
    updatedAnswer = False
    if answerRequest.status_code == 200:
        return bool_answer
    return None

def outOfTime():
    session["startTime"] = session.get('startTime', None)
    session["studyDuration"] = session.get('studyDuration', None)
    if session["startTime"] and session["studyDuration"]:
        if time.time() - session["startTime"] > (session["studyDuration"])*60:
            return True
    return False

def lookupUser(phone_num):
    userRequest = requests.get(askiiUrl+'/users/phone_num/'+phone_num+"?key="+key)
    user = userRequest.json().get("user", None)
    if user:
        name = user.get("name", "")
        userId = getIdFromUri(user.get("uri", None))
        session["userId"] = userId
        return user
    return False

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

def createUser(name, phone_num):
    data = json.dumps({"name": name, "phone_num": phone_num})
    userRequest = requests.post(askiiUrl+'/users?key='+key, headers=headers, data=data)
    return userRequest.json()["user"]

@app.route("/", methods=['GET', 'POST'])
def index():
    """Respond with the number of text messages sent between two parties."""
    if request.values.get('From', None) == None:
        return 'Welcome to the US Naturalization Certification Demo'

    # session.clear()
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
        userText = request.values.get('Body', None)
        if session.get('currentQuestion', None) and userText:
            answer = answerQuestion(session["userId"], session["currentQuestion"], userText)
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
            timeoutSession()
            session["welcomeStep"] = session.get("welcomeStep", 0)
            if session["welcomeStep"] == 0:
                message = "Welcome to Askii! To get started, what is your first name?"
                resp = twilio.twiml.Response()
                resp.sms(message)
                session["welcomeStep"] += 1
                return str(resp)
            if session["welcomeStep"] == 1:
                name = request.values.get('Body')
                user = createUser(name, phone_num)
                del session["welcomeStep"]
                message = "Welcome, "+user.get("name", "")+"! How much time do you have to study today?"
                resp = twilio.twiml.Response()
                resp.sms(message)
                session["step"] = 1
                session["prevTime"] = time.time()
                return str(resp)
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
                userText = request.values.get('Body', None)
                session["attempt"] = session.get("attempt", 0)
                if session["currentQuestion"] and userText:
                    answer = answerQuestion(session["userId"], session["currentQuestion"], userText)
                    # print answer
                    if answer == False:
                        if session["attempt"]==0:
                            message = formatHint(session["currentQuestion"])
                            resp = twilio.twiml.Response()
                            resp.sms(message)
                            session["attempt"]+=1
                            return str(resp)
                            # give hint
                        elif session["attempt"]==1:
                            message = formatInfoHint(session["currentQuestion"])
                            resp = twilio.twiml.Response()
                            resp.sms(message)
                            session["attempt"]+=1
                            return str(resp)

                        elif session["attempt"]==2:
                            message = incorrentAndGetQuestion(session["userId"], session["counter"])
                            resp = twilio.twiml.Response()
                            resp.sms(message)
                            session["counter"] += 1
                            session["attempt"]=0
                            return str(resp)
                            # come back to question, get next question

                # add in yay! correct
                message = correctAndGetQuestion(session["userId"], session["counter"])
                resp = twilio.twiml.Response()
                resp.sms(message)
                session["counter"] += 1
                return str(resp)
    
    return str('done')

 
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
