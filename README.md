# drone file upload download
Application to automatically download and upload data from a drone to Azure cloud using raspberrypi memory card as a buffer.
 ## Setup
   - `mkdir /home/dbox/FileUpload` and scp files or
   - `scp -r /[LOCAL_PATH]/FileUpload dbox@[DBOX_IP]:/home/dbox/FileUpload/`
   - `python -m venv  /home/dbox/FileUpload/venv`
   
   - `source /home/dbox/FileUpload/venv/bin/activate`
   
   - `pip install azure-core azure-storage-blob azure-identity protobuf psutil paho-mqtt pyudev pyyaml pillow`
   
   - `chmod +x /home/dbox/FileUpload/main.py`
   
   - `sudo nano /etc/systemd/system/file_upload_service.service` Service file in repository.
   
   - `sudo systemctl daemon-reload`
   
   - Optional, because of lag `sudo systemctl enable file_upload_service`
   
   - `sudo systemctl start file_upload_service`
 ## TODO
   - Needs testing in file upload to cloud.
   - Error handling
   - Testing
   - Refactoring
   - Splitting into files
   - Cleaning up
   
