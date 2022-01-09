from django.shortcuts import render
from django.http import HttpResponse
import requests,datetime,time
from django.core.files.storage import FileSystemStorage
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from .settings import env


class VideoAnalyzer:
    subscription_key = env('SUBSCRIPTION_KEY')
    account_id = env('ACCOUNT_ID')
    location = "TRIAL"  # change this if you have a paid subscription tied to a specific location
 
    def get_access_token(self):
        """
        Get an access token from the Video Indexer API. These expire every hour and are required in order to use the
        service.
        :return access_token: string.
        """
        url = "https://api.videoindexer.ai/Auth/{}/Accounts/{}/AccessToken?allowEdit=true".format(
           self.location,self.account_id
        )
        headers = {
            "Ocp-Apim-Subscription-Key":self.subscription_key,
        }
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            access_token = response.json()
            return access_token
        else:
            print("[*] Error when calling video indexer API.")
            print("[*] Response : {} {}".format(response.status_code, response.reason))

    def send_to_video_indexer(self, video_url, video_id,video_name, access_token):
        """
        Send a video to be analysed by video indexer.
        :param video_id: string, identifier for the video..
        :param video_url: string, public url for the video.
        :param access_token: string, required to use the API.
        :return video_indexer_id: string, used to access video details once indexing complete.
        """

        # Set request headers and url
        headers = {
            "Content-Type": "multipart/form-data",
            "Ocp-Apim-Subscription-Key": self.subscription_key,
        }
       
        video_indexer_url=f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos?name={video_name}&privacy=Private&videoUrl={video_url}&fileName={video_name}&accessToken={access_token}&sendSuccessEmail=True&streamingPreset=Default"
        # Make request and catch errors
        response = requests.post(url=video_indexer_url, headers=headers)
        if response.status_code == 200:
            video_indexer_id = response.json()["id"]
            return video_indexer_id
        # If the access token has expired get a new one
        if response.status_code == 401:
            print("[*] Access token has expired, retrying with new token.")
            access_token = self.get_access_token()
            video_indexer_new_url=f"https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos?name={video_name}&privacy=Private&videoUrl={video_url}&fileName=videofile1&accessToken={access_token}&sendSuccessEmail=True&streamingPreset=NoStreaming"
           
            response = requests.post(url=video_indexer_new_url, headers=headers)
            if response.status_code == 200:
                video_indexer_id = response.json()["id"]
                return video_indexer_id
            else:
                print("[*] Error after retrying.")
                print(
                    "[*] Response : {} {}".format(response.status_code, response.reason)
                )
        # If you are sending too many requests
        if response.status_code == 429:
            print("[*] Throttled for sending too many requests.")
            time_to_wait = response.headers["Retry-After"]
            print("[*] Retrying after {} seconds".format(time_to_wait))
            sleep(int(time_to_wait))
            response = requests.post(url=video_indexer_url, headers=headers)
            if response.status_code == 200:
                video_indexer_json_output = response.json()
                return video_indexer_json_output
            else:
                print("[*] Error after retrying following throttling.")
                print(
                    "[*] Response : {} {}".format(response.status_code, response.reason)
                )
        else:
            print("[*] Error when calling video indexer API.")
            print("[*] Response : {} {} {}".format(response.status_code, response.reason,response))
    
    def get_video_index(self,video_id,access_token):
        index_url=f'https://api.videoindexer.ai/{self.location}/Accounts/{self.account_id}/Videos/{video_id}/Index?accessToken={access_token}'

        index_res=requests.get(index_url)
        processingProgress =index_res.json()['videos'][0]['processingProgress']
        print(processingProgress)
        return processingProgress
            



def home(request):
    va=VideoAnalyzer()
    my_access_token=va.get_access_token()
    if request.method == 'POST' and request.FILES['mediafile']:
        myfile = request.FILES['mediafile']
        try:
            # Quick start code goes here
            # connect_str = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
            connect_str =env('CONNECTION_STR')
            # Create the BlobServiceClient object which will be used to create a container client
            blob_service_client = BlobServiceClient.from_connection_string(connect_str)

            # Create a unique name for the container
            container_name = 'frtcontainer'
            current_id=str(datetime.datetime.now())
            # Create the container
            blob_client = blob_service_client.get_blob_client(container=container_name, blob=(current_id+".mp4"))
            # container_client = blob_service_client.create_container(container_name) 
            blob_client.upload_blob(myfile)           
            response_id = va.send_to_video_indexer(
            video_url=blob_client.url,
            video_id=current_id,
            video_name=current_id,
            access_token=my_access_token,
            )
            return render(request, 'index.html',{'token':my_access_token,'videoid':response_id,'file_uploaded':True})
                    
        except Exception as ex:
            print('Exception:')
            print(ex)
            
        return render(request, 'index.html', {
            'file_uploaded': True,
        })
        
    return render(request, 'index.html')

