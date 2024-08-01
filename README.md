# drone file upload download
 ## Setup
   - `mkdir /home/dbox/FileUpload` and scp files or `scp -r /[LOCAL_PATH]/FileUpload dbox@[DBOX_IP]:/home/dbox/FileUpload/`
   
   - `python -m venv  /home/dbox/FileUpload/venv`
   
   - `source /home/dbox/FileUpload/venv/bin/activate`
   
   - `pip install azure-core azure-storage-blob azure-identity protobuf psutil paho-mqtt pyudev pyyaml pillow`
   
   - `chmod +x /home/dbox/FileUpload/main.py`
   
   - `sudo nano /etc/systemd/system/file_upload_service.service` Service file in repository.
   
   - `sudo systemctl daemon-reload`
   
   - `sudo systemctl enable file_upload_service`
   
   - `sudo systemctl start file_upload_service`
   
   
   
