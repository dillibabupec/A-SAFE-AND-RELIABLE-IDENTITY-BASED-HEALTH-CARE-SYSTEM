from flask import Flask,render_template,request,redirect,url_for, flash
from flask_pymongo import pymongo
from werkzeug.utils import secure_filename
from werkzeug.datastructures import  FileStorage
import base64
import os

import argon2, binascii
from decouple import config

import plotly
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import json
from datetime import datetime
import qrcode
from scanner import *

try:
    UPLOAD_FOLDER = 'uploadeddata/labrecords/'
    ALLOWED_EXTENSIONS = { 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

    app = Flask(__name__,
            static_url_path='', 
            static_folder='web/static',
            template_folder='web/templates')
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    CONNECTION_STRING = config('MONGO_URI') 
    client = pymongo.MongoClient(CONNECTION_STRING)
    db = client.get_database('healthhistory')

    users=db.patients
    qrcodes=db.qrcode
    history=db.medicalrecords

    clientname = ""
    clientmail = ""
    #app.config['MONGO_URI']="mongodb://localhost:27017/manager"
    #mongo=PyMongo(app)

    @app.route("/",methods=["POST","GET"])
    def index():
        return render_template("index.html") 
    
    @app.route("/adminlogin",methods=["POST","GET"])
    def adminlogin():
        return render_template("login.html")   
    @app.route("/adddetail",methods=["POST","GET"])
    def adddetail():
        return render_template("userdetail.html")
    @app.route("/getqrcode",methods=["POST","GET"])
    def getqrcode():
        return render_template("getqrcode.html")

    @app.route("/allowadmin",methods=["POST","GET"])
    def allowadmin():
        if request.method =='POST':
            name=request.form['name']
            password=request.form['pass']
      
            if(name == config('HH_ADMIN') and password == config('SECURE_KEY')):
                return render_template("setmedicalrecords.html")
        
        return render_template("login.html") 
                 
    @app.route("/savedetail",methods=["POST","GET"])
    def savedetail():
        message=''
        if request.method =='POST':
            name=request.form['name']
            gender=request.form['gender']
            age=request.form['age'] 
            email=request.form['email']
            phone=request.form['phone']
            address=request.form['address']
            city=request.form['city']
            state=request.form['state']
            zipcode=request.form['zipcode']

            name_lower = str(name).lower()
            email_lower = str(email).lower()

            encodedBytes = base64.b64encode(name_lower.encode("utf-8"))
            key_one =  str(encodedBytes, "utf-8")
            encodedBytes = base64.b64encode(email_lower.encode("utf-8"))
            key_two =  str(encodedBytes, "utf-8")

            identity = key_two+key_one
            identity = str.encode(identity)

            SECRET_KEY = config('SECRET_KEY')
            salt = str.encode(SECRET_KEY)

            hash = argon2.hash_password_raw(time_cost=16, memory_cost=2**15, parallelism=2, hash_len=32, password=identity, salt=salt, type=argon2.low_level.Type.ID)
            document_id = binascii.hexlify(hash)
            
            print(document_id)
            records = users.insert_one({"_id":document_id, "name":name_lower,"gender":gender,"age":age,"email":email,"phone":phone,"address":address,"city":city,"state":state,"zipcode":zipcode})
            codes   = qrcodes.insert_one({"_id":  document_id, "code": ''})

        return render_template("userdetail.html")

    @app.route("/getqr",methods=["POST","GET"])
    def getqr():
        message=''
        detail_one = ''
        detail_two = ''
        detail_three = ''
        detail_four = ''
        if request.method =='POST':
            name=request.form['name'].lower()
            email=request.form['email'].lower()
            phone=request.form['phone'] 

            details= users.find({"$and": [{"name":name,"email": email,"phone":phone}]})
            details_list = []
            for item in details:
                detail_obj = {
                    "Name"      : item['name'],
                    "Email"     : item['email'],
                    "Phone"     : item['phone'],
                    "Code"      : item['_id']
                }
                details_list.append(detail_obj)

            for i in details_list:
                detail_one =  i["Name"]
                detail_two =  i["Email"]
                detail_three =  i["Phone"]
                detail_four =  i["Code"]
            
            rawdata = str(detail_one)+'%'+str(detail_two)+'%'+str(detail_three)+'%'+str(detail_four)

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(rawdata)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            img.save('web/static/data/qrcode.png')
            
            filename = "web/static/data/qrcode.png"
            image = open(filename, 'rb')
            image_read = image.read()
            image_64_encode = base64.encodebytes(image_read) #encodestring also works aswell as decodestring

            print('This is the image in base64: ' + str(image_64_encode))

            qrcodes.update_one({"_id":detail_four},{"$set":{"code": str(image_64_encode) }})

        return render_template("qrdisplay.html")

    @app.route("/scanqr",methods=["POST","GET"])
    def scanqr():
        rawdata = scanqrcode()
        print(str(rawdata))
        
        list_details = rawdata.split('%', 3)
        global clientname, clientmail
        clientname  = str(list_details[0]).lower()
        clientmail = str(list_details[1]).lower()

        encodedBytes = base64.b64encode(clientname.encode("utf-8"))
        key_one =  str(encodedBytes, "utf-8")
        encodedBytes = base64.b64encode(clientmail.encode("utf-8"))
        key_two =  str(encodedBytes, "utf-8")

        identity = key_two+key_one
        identity = str.encode(identity)

        SECRET_KEY = config('SECRET_KEY')
        salt = str.encode(SECRET_KEY)

        hash = argon2.hash_password_raw(time_cost=16, memory_cost=2**15, parallelism=2, hash_len=32, password=identity, salt=salt, type=argon2.low_level.Type.ID)
        document_id = binascii.hexlify(hash)

        medicalhistory = history.find({"patientid": document_id})
        record_list = []
        for item in medicalhistory:
            record_obj = {
                "patientid"   : item['patientid'],
                "date"        : item['date'],
                "hospital"    : item['hospital'],
                "location"    : item['location'],
                "reason"      : item['reason'],
                "diagnosis"   : item['diagnosis'],
                "medicine"    : item['medicine'],
                "suggestion"  : item['suggestion'],
                "records"     : item['records']
            }
            record_list.append(record_obj)
            for i in record_list:
                print(str(i["patientid"])+i["hospital"])

        return render_template("medicalhistory.html", detail = record_list, name = clientname )
        

    @app.route("/saveonerecord",methods=["POST","GET"])
    def saveonerecord():
        if request.method == 'POST':
            encoded_string = ""
            medicalrecord = []
            medicalrecord.append(request.form['name'])
            medicalrecord.append(request.form['email'])
            medicalrecord.append(request.form['date'])
            medicalrecord.append(request.form['hospital'])
            medicalrecord.append(request.form['location'])
            medicalrecord.append(request.form['reason'])
            medicalrecord.append(request.form['diagnosis'])
            medicalrecord.append(request.form['medicine'])
            medicalrecord.append(request.form['suggestion'])
            medicalrecord.append(request.form['habit'])

            name_lower = str(medicalrecord[0]).lower()
            email_lower = str(medicalrecord[1]).lower()

            encodedBytes = base64.b64encode(name_lower.encode("utf-8"))
            key_one =  str(encodedBytes, "utf-8")
            encodedBytes = base64.b64encode(email_lower.encode("utf-8"))
            key_two =  str(encodedBytes, "utf-8")

            identity = key_two+key_one
            identity = str.encode(identity)

            SECRET_KEY = config('SECRET_KEY')
            salt = str.encode(SECRET_KEY)

            hash = argon2.hash_password_raw(time_cost=16, memory_cost=2**15, parallelism=2, hash_len=32, password=identity, salt=salt, type=argon2.low_level.Type.ID)
            document_id = binascii.hexlify(hash)


            file = request.files['file']

            if file.filename == '':
                flash('No selected file')
                return redirect("/enterrecords")
            if file:
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                # return redirect(url_for('download_file', name=filename))
                with open(os.path.join(app.config['UPLOAD_FOLDER'], filename), "rb") as pdf_file:
                    encoded_string = base64.b64encode(pdf_file.read())
                    print(encoded_string)
            print(medicalrecord[0]+medicalrecord[2]+medicalrecord[4]+medicalrecord[6]+str(document_id))

            docs = history.insert_one({"patientid":document_id, "date":medicalrecord[2], "hospital":medicalrecord[3],"location":medicalrecord[4],
                    "reason":medicalrecord[5],"diagnosis":medicalrecord[6],
                    "medicine":medicalrecord[7],"suggestion":medicalrecord[8],"habit":medicalrecord[9],"records":encoded_string})

            medicalhistory = history.find({"patientid": document_id})
            record_list = []
            for item in medicalhistory:
                record_obj = {
                    "patientid"   : item['patientid'],
                    "date"        : item['date'],
                    "hospital"    : item['hospital'],
                    "location"    : item['location'],
                    "reason"      : item['reason'],
                    "diagnosis"   : item['diagnosis'],
                    "medicine"    : item['medicine'],
                    "suggestion"  : item['suggestion'],
                    "records"     : item['records']
                }
                record_list.append(record_obj)
        
        return render_template("medicalhistory.html", detail = record_list, name = medicalrecord[0])

    @app.route("/showrecord",methods=["POST","GET"])
    def showrecord():
        recid = ''
        date = request.args.get("recordid")
        print(date)

        global clientname, clientmail
        encodedBytes = base64.b64encode(clientname.encode("utf-8"))
        key_one =  str(encodedBytes, "utf-8")
        encodedBytes = base64.b64encode(clientmail.encode("utf-8"))
        key_two =  str(encodedBytes, "utf-8")

        identity = key_two+key_one
        identity = str.encode(identity)

        SECRET_KEY = config('SECRET_KEY')
        salt = str.encode(SECRET_KEY)

        hash = argon2.hash_password_raw(time_cost=16, memory_cost=2**15, parallelism=2, hash_len=32, password=identity, salt=salt, type=argon2.low_level.Type.ID)
        document_id = binascii.hexlify(hash)

        medicalhistory = history.find({"$and" : [{"patientid": document_id,"date":date}]})
        record_list = []
        for item in medicalhistory:
            recid = item['records']

        print("??????????????????->"+str(recid))
        bytes = base64.b64decode(recid, validate=True)
        print("??????????????????->"+str(bytes))
        f = open('web/static/displayrecords/file.pdf', 'wb') 
        f.write(bytes)
        f.close
        return render_template("labrecord.html")

    def create_burst():

        data = dict(
        character=["Diagnosis", "Head", "Spine", "Common Illness", "Brain", "Knee", "Migrane", "Nerve Weakness", "Marrow Surgery", "Cold & Cough", "Fever", "Blood Leak", "Mental Sickness", "Cartilage Rupture", "Arthritis", "Bone Rupture"],
        parent=["", "Diagnosis", "Diagnosis", "Diagnosis", "Diagnosis", "Diagnosis", "Head", "Head", "Spine", "Common Illness", "Common Illness" , "Brain", "Brain", "Knee", "Knee", "Knee"],
        value=[0, 40, 20, 100, 60, 35, 15, 25, 20, 30, 70, 25, 35, 9, 8, 18])
        fig =px.sunburst(
            data,
            names='character',
            parents='parent',
            values='value',
        )
       
        fig.update_layout(margin = dict(t=50, l=0, r=0, b=0))

        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return graphJSON

    def create_bar():

        xdata = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec'] 
        ydata = [300, 30, 75, 180, 607, 21, 80, 91, 11, 220, 455, 90]
        
        fig = px.bar(x= xdata, y= ydata, color= ydata)

        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return graphJSON

    def create_pie():

        nam = ['Male', 'Female', 'Others'] 
        val = [2800, 4250, 150]
        
        fig = px.pie(values= val,names= nam,color_discrete_sequence=px.colors.sequential.RdBu)
        fig.update_layout(margin = dict(t=50, l=0, r=0, b=0))

        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return graphJSON

    def create_oryel():

        case = [684,321,191,616,526,86,177,546,949,586,999,221,
                610,429,319,698,273,131,253,85,459,263,363,438,
                117,800,26,479,657,350,520,189,578,41,63,543,
                780,260,106,635,162,387,127,224,278,307,246,167,
                300, 30, 75, 180, 607, 21, 80, 91, 11, 220, 455, 90,
                345,588,723,770,315,228
                ]
        month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec',
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec',
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec',
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec',
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec',
                'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun' ]
        year = ['2016','2016','2016','2016','2016','2016','2016','2016','2016','2016','2016','2016',
                 '2017','2017','2017','2017','2017','2017','2017','2017','2017','2017','2017','2017',
                 '2018','2018','2018','2018','2018','2018','2018','2018','2018','2018','2018','2018',
                 '2019','2019','2019','2019','2019','2019','2019','2019','2019','2019','2019','2019',
                 '2020','2020','2020','2020','2020','2020','2020','2020','2020','2020','2020','2020',
                 '2021','2021','2021','2021','2021','2021' ] 
        df = pd.DataFrame(
            dict(year = year, month = month, case = case)
        )
        fig = px.sunburst(df, path=[year, month, case],color= case,color_continuous_scale='mint') 
        fig.update_layout(margin = dict(t=0, l=0, r=0, b=0))

        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return graphJSON

    def create_bubble():
        
        month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec','Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct',' Nov', 'Dec']
        case = [117,800,26,479,657,350,520,189,578,41,63,543,177,156,154,694,521,633,377,274,355,178,716,330]
        gender = ['Male','Male','Male','Male','Male','Male','Male','Male','Male','Male','Male','Male', 'Female','Female','Female','Female','Female','Female','Female','Female','Female','Female','Female','Female' ]
        df = pd.DataFrame(
            dict(month = month, case = case, gender = gender)
        )
        fig = px.scatter(df, x = month, y = gender, size =  case,color = case,size_max=100)
        fig.update_layout(xaxis_title = 'Pages', yaxis_title = 'Ratings')

        graphJSON = json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)
        return graphJSON

    @app.route("/showgraph",methods=["POST","GET"])
    def showgraph():
        patient_record, cases_count, gender_ratio  = create_burst(), create_bar(), create_pie()
        case_graph,case_wise  = create_oryel(), create_bubble()
        return render_template('graphs.html',plot1 = patient_record, plot2 = cases_count, plot3 = gender_ratio, plot4 = case_graph, plot5 = case_wise)
    
except Exception as e:
    print(e)

if __name__ == "__main__":
    
    app.run(host="0.0.0.0",port=5000,debug=True)
