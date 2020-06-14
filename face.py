import cv2
import numpy as np
import datetime

#ObjectStorage
import ibm_boto3
from ibm_botocore.client import Config, ClientError

#CloudantDB
from cloudant.client import Cloudant
from cloudant.error import CloudantException
from cloudant.result import Result, ResultByKey
import requests

import json
from watson_developer_cloud import VisualRecognitionV3

import time
import sys
import ibmiotf.application
import ibmiotf.device
import random
#Provide your IBM Watson Device Credentials
organization = "0l3mtb"
deviceType = "raspberrypi"
deviceId = "123456"
authMethod = "token"
authToken = "12345678"

visual_recognition = VisualRecognitionV3(
    '2018-03-19',
    iam_apikey='41ufY2T9ZhQUxZg7FuNCCsGLYstvYU_lZCb9ESc_FzSZ')


# Constants for IBM COS values
COS_ENDPOINT = "https://s3.jp-tok.cloud-object-storage.appdomain.cloud" # Current list avaiable at https://control.cloud-object-storage.cloud.ibm.com/v2/endpoints
COS_API_KEY_ID = "Qo2Za_6450oKGeIuPLU-TdJjgPCXjlo9D1RaACbgg2qi" # eg "W00YiRnLW4a3fTjMB-odB-2ySfTrFBIQQWanc--P3byk"
COS_AUTH_ENDPOINT = "https://iam.cloud.ibm.com/identity/token"
COS_RESOURCE_CRN = "crn:v1:bluemix:public:cloud-object-storage:global:a/95c966e28a7346a4a248f295fbaecccb:0a7a79b6-f03b-4dd9-b6fc-2306f6010537::" # eg "crn:v1:bluemix:public:cloud-object-storage:global:a/3bf0d9003abfb5d29761c3e97696b71c:d6f04d83-6c4f-4a62-a165-696756d63903::"
# Create resource
cos = ibm_boto3.resource("s3",
    ibm_api_key_id=COS_API_KEY_ID,
    ibm_service_instance_id=COS_RESOURCE_CRN,
    ibm_auth_endpoint=COS_AUTH_ENDPOINT,
    config=Config(signature_version="oauth"),
    endpoint_url=COS_ENDPOINT
)

#Provide CloudantDB credentials such as username,password and url

client = Cloudant("4eb3d1ab-4cde-44e2-ae43-59ca49f07d9e-bluemix", "41199fcc219b18f411e5f5b5fb2d0a0ef3f89e6f0dc0316efa8c50f29e697574", url="https://4eb3d1ab-4cde-44e2-ae43-59ca49f07d9e-bluemix:41199fcc219b18f411e5f5b5fb2d0a0ef3f89e6f0dc0316efa8c50f29e697574@4eb3d1ab-4cde-44e2-ae43-59ca49f07d9e-bluemix.cloudantnosqldb.appdomain.cloud")
client.connect()

#Provide your database name

database_name = "problem"

my_database = client.create_database(database_name)

if my_database.exists():
   print(f"'{database_name}' successfully created.")

def myCommandCallback(cmd):
        print("Command received: %s" % cmd.data)#Commands
        print(type(cmd.data))
        i=cmd.data['command']
        if i=='Sprinkler ON':
                print("Sprinkler is ON")
        elif i=='Sprinkler OFF':
                print("Sprinkler is OFF")

try:
	deviceOptions = {"org": organization, "type": deviceType, "id": deviceId, "auth-method": authMethod, "auth-token": authToken}
	deviceCli = ibmiotf.device.Client(deviceOptions)
	#..............................................
	
except Exception as e:
	print("Caught exception connecting device: %s" % str(e))
	sys.exit()

# Connect and send a datapoint "hello" with value "world" into the cloud as an event of type "greeting" 10 times
deviceCli.connect()


def vis(a):
   with open(a, 'rb') as images_file:
    a = visual_recognition.classify(
        images_file,
        threshold='0.6',
	classifier_ids='chanikya_2040677521').get_result()
   #print(json.dumps(a, indent=2))
   b=a["images"][0]["classifiers"][0]["classes"][0]["class"]
   return b


def multi_part_upload(bucket_name, item_name, file_path):
    try:
        print("Starting file transfer for {0} to bucket: {1}\n".format(item_name, bucket_name))
        # set 5 MB chunks
        part_size = 1024 * 1024 * 5

        # set threadhold to 15 MB
        file_threshold = 1024 * 1024 * 15

        # set the transfer threshold and chunk size
        transfer_config = ibm_boto3.s3.transfer.TransferConfig(
            multipart_threshold=file_threshold,
            multipart_chunksize=part_size
        )

        # the upload_fileobj method will automatically execute a multi-part upload
        # in 5 MB chunks for all files over 15 MB
        with open(file_path, "rb") as file_data:
            cos.Object(bucket_name, item_name).upload_fileobj(
                Fileobj=file_data,
                Config=transfer_config
            )

        print("Transfer for {0} Complete!\n".format(item_name))
    except ClientError as be:
        print("CLIENT ERROR: {0}\n".format(be))
    except Exception as e:
        print("Unable to complete multi-part upload: {0}".format(e))


#It will read the first frame/image of the video
video=cv2.VideoCapture(0)

while True:
   #capture the first frame
   check,frame=video.read()
   gray=cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
   cv2.imshow('Face detection', frame)
   picname=datetime.datetime.now().strftime("%y-%m-%d-%H-%M")
   cv2.imwrite(picname+".jpg",frame)
   a=vis(picname+".jpg")
   print(a)
   temp =random.randint(30, 80)
   #Send Temperature & Humidity to IBM Watson
   flamesensor=random.randint(700,1000)#units in nm
   #print(firesensor)
   Mq6=random.randint(100,10000)#units in ppm isobutane
   #print(Mq6)
   data = { 'Temperature' : temp, 'FlameSensor': flamesensor,'MQ6': Mq6}
   #print (data)
   def myOnPublishCallback():
      print ("Published Temperature = %s C" % temp, "FlameSensor = %s nm" % flamesensor,"Mq6=%s ppm"% Mq6, "to IBM Watson")
   success = deviceCli.publishEvent("Weather", "json", data, qos=0, on_publish=myOnPublishCallback)
   if not success:
      print("Not connected to IoTF")
   time.sleep(2)
   deviceCli.commandCallback = myCommandCallback#subscription
   if a=="fire":
      multi_part_upload("chanikya2", picname+".jpg", picname+".jpg")
      json_document={"link":COS_ENDPOINT+"/"+"chanikya2"+"/"+picname+".jpg"}
      new_document = my_database.create_document(json_document)
      # Check that the document exists in the database.
      if new_document.exists():
         print(f"Document successfully created.")
      r = requests.get('https://www.fast2sms.com/dev/bulk?authorization=FEcl3Tw5s069IPiedqHkXLgbKYRxuVJnQ8vfO4mANUr2hjyBWz9b4juKklE5MvfDT2pHGBQhtXnRac8x&sender_id=FSTSMS&message=Fire!!Fire!!&language=english&route=p&numbers=9666321361')
      print(r.status_code)

   #waitKey(1)- for every 1 millisecond new frame will be captured
   Key=cv2.waitKey(1)
   if Key==ord('q'):
      #release the camera
      video.release()
      #destroy all windows
      cv2.destroyAllWindows()
      break

