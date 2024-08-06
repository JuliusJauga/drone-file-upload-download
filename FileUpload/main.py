import multiprocessing.queues
import psutil
import os
import subprocess
import re
import json
import time
import multiprocessing
import concurrent.futures
from typing import Optional, List, Dict
from datetime import datetime
from azure.storage.blob import BlobServiceClient, ContainerClient
from azure.identity import DefaultAzureCredential
from azure.core.exceptions import ResourceExistsError, ServiceRequestError, ServiceResponseError

from PIL import Image
from PIL.ExifTags import TAGS

import paho.mqtt.client as mqtt
import pyudev
import yaml

from box_upload_api_pb2 import UploadState, DownloadAllowance, DownloadStateStream, DownloadAllowanceStream, DownloadAllowanceRequest, DownloadResponse, CloudUploadStateStream, CloudUploadAllowanceStream, CloudUploadAllowance, DownloadMode, DownloadState


# Dependencies: azure-core, pyudev, paho-mqtt, pillow, azure-storage-blob, azure-identity, protobuf, psutil

class ConfigYAML:
    def __init__(self, config_file: str) -> None:
        self._config = self._load_config(config_file)

    def _load_config(self, config_file: str) -> dict:
        with open(config_file, 'r') as file:
            return yaml.safe_load(file)

    def get(self, key: str, default=None) -> Optional[dict]:
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
        except KeyError:
            print("Failed to retrieve config field.")
            return default
        return value
class ConfigJSON:
    def __init__(self, config_file: str) -> None:
        self._config = self._load_config(config_file)

    def _load_config(self, config_file: str) -> dict:
        with open(config_file, 'r') as file:
            return json.load(file)

    def get(self, key: str, default=None) -> Optional[dict]:
        keys = key.split('.')
        value = self._config
        try:
            for k in keys:
                value = value[k]
        except KeyError:
            return default
        return value


class AzureStorage:
    def __init__(self, storage_account_name: str, azure_connection_file_name: str, chunk_size: str) -> None:
        self.storage_account_name = storage_account_name
        self.azure_connection_file_name = azure_connection_file_name
        self.blob_service_client = None
        try:
            result = float(chunk_size)
            self.chunk_size = result
        except ValueError:
            self.chunk_size = float(1)
        if not self.connect_to_azure():
            print("Could not connect azure")
            exit(1)
        self.uploaded_bytes = 0
        self.total_bytes = 0
    def connect_to_azure(self) -> bool:
        connect_atempts = 10
        attempts = 0
        while attempts < connect_atempts:
            self.connect_with_connection_string()
            if not self.blob_service_client:
                credential = DefaultAzureCredential()
                account_url = f"https://{self.storage_account_name}.blob.core.windows.net"
                self.blob_service_client = BlobServiceClient(account_url, credential=credential, max_block_size=int(self.chunk_size*1024), max_single_put_size=int(self.chunk_size*1024))
            if self.check_connection():
                return True
            else:
                attempts += 1
                print(f"Failed to connect to Azure Storage account. Attempt {attempts} of {connect_atempts}. Retrying...")
                time.sleep(5)
        return False
    def connect_with_connection_string(self) -> bool:
        path_to_file = os.path.dirname(__file__)
        path_to_file = os.path.join(path_to_file, self.azure_connection_file_name)
        try:
            if self.azure_connection_file_name.endswith('.json'):
                with open(path_to_file, 'r') as file:
                    data = json.load(file)
                connection_string = data.get("connectionString")
                if not connection_string:
                    print("Connection string not found in the JSON file.")
                    return False
            elif self.azure_connection_file_name.endswith('.txt'):
                with open(path_to_file, 'r') as file:
                    connection_string = file.read()
                if not connection_string:
                    print("Connection string not found in the TXT file.")
                    return False
            elif self.azure_connection_file_name.endswith('.yaml'):
                with open(path_to_file, 'r') as file:
                    data = yaml.safe_load(file)
                connection_string = data.get("connectionString")
                if not connection_string:
                    print("Connection string not found in the YAML file.")
                    return False
            self.blob_service_client = BlobServiceClient.from_connection_string(connection_string,max_block_size=int(1024*self.chunk_size), max_single_put_size=int(1024*self.chunk_size))
            print("Successfully connected to Azure Storage account.")
            return True
        except FileNotFoundError:
            print(f"Connection file not found.")
            return False
        
        except Exception as e:
            print(f"An error occurred: {e}")
            return False 
    def check_connection(self) -> bool:
        try:
            containers = self.blob_service_client.list_containers()
            return True
        except Exception as e:
            print(f"Failed to list containers: {e}")
            return False
    def upload_blob(self, container_name, file: str, file_path: str, blob_name: str, in_progress_word: str, stop_signal: multiprocessing.Event) -> bool:
        while not stop_signal.is_set():
            try:
                with open(file_path, "rb") as data:
                    proxy_name = blob_name.replace(f"_{in_progress_word}", "")
                    container = self.blob_service_client.get_container_client(container_name)
                    container.upload_blob(name=proxy_name, data=data, overwrite=True)
                print(f"UPLOADING {file} SUCCESS")
                return True
            except (ServiceRequestError, ServiceResponseError) as e:
                print(f"Failed to upload {file_path}, retrying...")
                print(f"Error type: {type(e).__name__}")
                print(f"Error message: {e}")
                continue
            except ResourceExistsError as e:
                print(f"File {file} already exists in the container. Skipping...")
                return True
            except FileNotFoundError as e:
                return False
        return False
    
    def get_container(self, container_name: str) -> ContainerClient:
        return self.blob_service_client.get_container_client(container_name)
    
    def send_data_drone(self, output_folder_path: str, subfolder_name: str, container_name: str, in_progress_word: str, stop_signal: multiprocessing.Event, queue: multiprocessing.Queue, time_interval) -> Optional[List[str]]:
        folder_path = os.path.join(output_folder_path, subfolder_name)
        uploaded_file_names = []
        if not os.path.exists(folder_path) or not os.path.isdir(folder_path):
            return
        try:
            for file in os.listdir(folder_path):
                if stop_signal.is_set():
                    print("Stopping sending process")
                    break
                if not is_jpeg_by_filename(file) or in_progress_word in file:
                    continue
                file_path = os.path.join(folder_path, file)
                blob_name = os.path.join(subfolder_name, file).replace(os.sep, '/')
                start_time = time.time()
                if self.upload_blob(container_name, file, file_path, blob_name, in_progress_word, stop_signal):
                    uploaded_file_names.append(file)
                    self.uploaded_bytes += os.path.getsize(file_path)
                    current_time = time.time()
                    if current_time - start_time >= time_interval:
                        start_time = current_time
                        data = (UploadState.IN_PROGRESS, self.uploaded_bytes, self.total_bytes)
                        queue.put(data)
        except FileNotFoundError as e:
            ...
        return uploaded_file_names

class DeviceManager:
    def __init__(self, input_device_name: str, input_device_mount_point: str, drone_vendor_id: str, image_folder_path: str, output_folder_path: str, time_interval: int, chunk_size: int, dbox_index: str) -> None:
        self.input_device_mount_point = os.path.join(input_device_mount_point, input_device_name)
        self.dbox_index = dbox_index

        self.drone_vendor_id = drone_vendor_id
        self.image_folder_path = image_folder_path
        self.output_folder_path = output_folder_path
        self.drone_mount_point = None
        
        self.time_interval = time_interval
        self.chunk_size = chunk_size
        self.moved_data = 0
        self.drone_folder_size = 0
        
        dbox_index = str(dbox_index)
        os.makedirs(os.path.join(self.output_folder_path, dbox_index), exist_ok=True)
    def listen_for_drone(self, queue: multiprocessing.Queue, stop_signal: multiprocessing.Event) -> None:
        while True:
            if stop_signal.is_set():
                print("Listening for drone halted")
                time.sleep(self.time_interval)
                continue
            context = pyudev.Context()
            for device in context.list_devices(subsystem='usb'):
                if device.get('ID_VENDOR_ID') == self.drone_vendor_id:
                    for child in device.children:
                        if child.subsystem == 'block':
                            print(f"Device found: {child.device_node}")
                            updated_queue = False
                            while stop_signal.is_set():
                                print("Mount not allowed")
                                if not updated_queue:
                                    queue.put((DownloadState.NOT_MOUNTED, self.moved_data, self.drone_folder_size))
                                    updated_queue = True
                                time.sleep(self.time_interval)
                            self.handle_drone_mounting(child.device_node)
                            self.drone_device_name = device.get('ID_MODEL')
                            self.drone_device = child.device_node
                            return
        
    def handle_drone_mounting(self, device: str) -> None:
        #/dev/sda
        self.drone_mount_point = self.check_if_mounted(device)
        while self.drone_mount_point is None:
            self.mount_disk(device, self.input_device_mount_point)
            self.drone_mount_point = self.check_if_mounted(device)
    def unmount_drone(self) -> None:
        if self.drone_mount_point is not None:
            self.unmount_disk(self.drone_device, self.drone_mount_point)
    def move_data_from_drone(self, folder_name: str, chunk_size: int, stop_signal: multiprocessing.Event, queue: multiprocessing.Queue) -> None:
        folder_name = str(folder_name)
        source_path = os.path.join(self.drone_mount_point, self.image_folder_path)
        folder_list = os.listdir(source_path)
        for folder in folder_list:
            self.drone_folder_size = self.get_folder_size(os.path.join(source_path, folder))
        print(self.drone_folder_size, end=" ")
        print(" bytes")
        self.moved_data = 0
        #files = os.listdir(source_path)
        #if not files:
        #    return
        for folder in folder_list:
            files = os.listdir(os.path.join(source_path, folder))
            destination_folder = os.path.join(self.output_folder_path, folder_name, folder)
            if not os.path.exists(destination_folder):
                os.makedirs(destination_folder)
            def move_file(file: str) -> int:
                if stop_signal.is_set():
                    return 0
                source = os.path.join(source_path, folder, file)
                destination = os.path.join(destination_folder, file)
                try:
                    if not os.path.exists(destination_folder):
                        os.makedirs(destination_folder)
                    file_size = os.path.getsize(source)
                    
                    if move_file_in_chunks(source, destination, chunk_size, stop_signal):
                        print(f"Finished moving file {file} ({file_size})")
                        return file_size
                    else:
                        return 0
                except FileNotFoundError as e:
                    print("File gone when moving")
                    return 0
            def move_file_in_chunks(source_path: str, destination_path: str, chunk_size: int, stop_signal: multiprocessing.Event) -> bool:
                if stop_signal.is_set():
                    return False
                if os.path.isdir(source_path):
                    return False
                with open(source_path, 'rb') as file:
                    with open(destination_path, 'wb') as destination_file:
                        while True:
                            if stop_signal.is_set():
                                print("Moving process interrupted, deleting destination file")
                                try:
                                    os.remove(destination_path)
                                except OSError as e:
                                    print(f"Error deleting destination file: {e}")
                                return False
                            chunk = file.read(chunk_size * 1024)
                            if not chunk:
                                break
                            destination_file.write(chunk)
                #os.remove(source_path) # OPTIONAL
                return True
            start_time = time.time()
            with concurrent.futures.ThreadPoolExecutor() as executor:
                futures = {executor.submit(move_file, file): file for file in files}
                while futures:
                    #concurrent.futures.wait(futures)
                    for future in concurrent.futures.as_completed(futures):
                        current_time = time.time()
                        if current_time - start_time >= self.time_interval:
                            start_time = current_time
                            data = (DownloadState.BUSY, self.moved_data, self.drone_folder_size)
                            queue.put(data)
                        self.moved_data += future.result()
                        futures.pop(future)
            if stop_signal.is_set():
                print("Moving process interrupted")
                return
        print("Finished moving all files")
        return

    def get_folder_size(self, folder_path: str) -> int:
        size = 0
        files = os.listdir(folder_path)
        for file in files:
            if is_jpeg_by_filename(file):
                file_path = os.path.join(folder_path, file)
                size += os.path.getsize(file_path)
        return size
    def find_latest_image_drone(self) -> Optional[datetime]:
        counter = 0
        latest_date = None
        folder_path = os.path.join(self.drone_mount_point, self.image_folder_path)
        for file in os.listdir(folder_path):
            file_path = os.path.join(self.drone_mount_point, self.image_folder_path, file)
            if os.path.isfile(file_path) and is_jpeg_by_filename(file):
                if self.get_image_creation_date(file_path) is None:
                    continue
                if counter == 0:
                    latest_date = self.get_image_creation_date(file_path)
                
                else:
                    current_date = self.get_image_creation_date(file_path)
                    if current_date > latest_date:
                        latest_date = current_date
                counter += 1
        return latest_date
    def rename_folder_drone(self, folder_name: str, in_progress_word: str) -> None:
        try:
            folder_path = os.path.join(self.output_folder_path, folder_name)
            new_folder_name = f"{folder_name}_{in_progress_word}"
            new_folder_path = os.path.join(self.output_folder_path, new_folder_name)
            os.rename(folder_path, new_folder_path)
        except FileNotFoundError as e:
            print("Folder not found skipping")
    def rename_folders_drone(self, path: str, in_progress_word) -> None:
        folders = os.listdir(path)
        for folder in folders:
            folder_path = os.path.join(path, folder)
            if in_progress_word in folder:
                continue
            try:
                new_folder_name = f"{folder}_{in_progress_word}"
                new_folder_path = os.path.join(path, new_folder_name)
                os.rename(folder_path, new_folder_path)    
            except Exception as e:
                new_folder_name = f"{folder}_{in_progress_word} (Copy)"
                new_folder_path = os.path.join(path, new_folder_name)
                os.rename(folder_path, new_folder_path)

    def rename_files_drone(self, folder_name: str, files: List[str], in_progress_word: str, dbox_index: int) -> None:
        dbox_index = str(dbox_index)
        folder_path = os.path.join(self.output_folder_path, dbox_index, folder_name)
        for file in files:
            file_path = os.path.join(folder_path, file)
            new_file_name = file.replace(file, in_progress_word)
            new_file_path = os.path.join(folder_path, new_file_name)
            try:
                os.rename(file_path, new_file_path)
            except FileNotFoundError:
                print("File gone while renaming")
                continue
    def get_folder_names_drone(self, dbox_index: int) -> None:
        folders = []
        dbox_index = str(dbox_index)
        if not os.path.exists(self.output_folder_path):
            return folders
        path = os.path.join(self.output_folder_path, dbox_index)
        folders_ = os.listdir(path)
        for item in folders_:
            item_path = os.path.join(self.output_folder_path, item)
            if os.path.isdir(item_path) and item != "System Volume Information" and item != ".Trash-1000":
                folders.append(item)
        return folders
    def wait_for_disconnect_drone(self) -> None:
        while True:
            found = False
            disk_labels = self.get_disk_labels()
            for device, label in disk_labels.items():
                if (device == self.drone_device):
                    found = True
                    print("Waiting for drone to disconnect")
                    time.sleep(5)
            if not found:
                print("Drone disconnected")
                return
    def check_if_mounted(self, device_name: str) -> Optional[str]:
        for partition in psutil.disk_partitions():
            if not device_name == partition.device:
                continue
            print(" is mounted")
            return partition.mountpoint
        print(" is not mounted")
        return None
    def get_disk_labels(self) -> Dict[str, str]:
        try:
            blkid_output = subprocess.run(['sudo', 'blkid'], capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            print(f"Error executing blkid: {e}")
            print(f"Return code: {e.returncode}")
            print(f"Output: {e.output}")
            print(f"Stderr: {e.stderr}")
            return {}
        disk_labels = {}
        for line in blkid_output.stdout.strip().split('\n'):
            match = re.search(r'(/dev/[\w\d]+):.*LABEL="([^"]+)"', line)
            if match:
                device = match.group(1)
                label = match.group(2)
                disk_labels[device] = label
        return disk_labels
    def mount_disk(self, device: str, mount_point: str) -> None:
        username = os.getlogin()
        subprocess.run(['sudo', 'mkdir', '-p', mount_point], check=True)
        command = f'rw,uid={username},gid={username}'
        result = subprocess.run(['sudo', 'mount', '-o', command, device, mount_point], check=True)
        if result.returncode == 0:
            print(f"Disk {device} mounted successfully at {mount_point}.")
        else:
            print(f"Failed to mount disk {device}. Error: {result.stderr.decode('utf-8')}")
    def unmount_disk(self, device: str, mount_point: str) -> None:
        result = subprocess.run(['sudo', 'umount', mount_point], capture_output=True)
        if result.returncode == 0:
            print(f"Disk {device} unmounted successfully from {mount_point}.")
        else:
            print(f"Failed to unmount disk {device}. Error: {result.stderr.decode('utf-8')}")
        if self.check_if_mounted(device):
            result = subprocess.run(['sudo', 'umount', device], capture_output=True)
            if result.returncode == 0:
                print(f"Disk {device} unmounted successfully.")
            else:
                print(f"Failed to unmount disk {device}. Error: {result.stderr.decode('utf-8')}")
    
    def get_image_creation_date(self, image_path: str) -> Optional[datetime]:
        try:
            with Image.open(image_path) as img:
                exif_data = img._getexif()
                if exif_data is not None:
                    for tag, value in exif_data.items():
                        tag_name = TAGS.get(tag, tag)
                        if tag_name == 'DateTimeOriginal':
                            return datetime.strptime(value, '%Y:%m:%d %H:%M:%S')
                return None
        except OSError as e:
            print(f"Error reading image file: {e}")
            return None
    def make_subfolder_name(self) -> str:
        current_time = self.find_latest_image_drone()
        if current_time is not None:
            current_time = current_time.strftime('%Y%m%d_%H%M%S')
        else:
            current_time = time.time()
            current_time = datetime.fromtimestamp(current_time).strftime('%Y%m%d_%H%M%S')
        subfolder_name = f"{self.drone_device_name}_{current_time}"
        return subfolder_name
class ProcessHandler:
    def __init__(self, azure_storage: AzureStorage, device_manager: DeviceManager, in_progress_word: str, container_name: str, mqtt_client: mqtt.Client, MQTT_TOPIC_DWNSTR: str, MQTT_TOPIC_UPLSTR: str, MQTT_TOPIC_DWNRES: str, MQTT_TOPIC_UPLREQ: str, MQTT_TOPIC_DWNREQ: str) -> None:
        self.azure_storage = azure_storage
        self.device_manager = device_manager
        self.in_progress_word = in_progress_word
        self.container_name = container_name


        self.queue_download = multiprocessing.Queue()
        self.queue_upload = multiprocessing.Queue()
        self.queue_response = multiprocessing.Queue()


        self.stop_signal_sending = multiprocessing.Event()
        self.stop_signal_moving = multiprocessing.Event()
        self.stop_signal_trash = multiprocessing.Event()
        self.stop_signal_download = multiprocessing.Event()


        self.move_process = multiprocessing.Process(target=self.handle_moving_process, args=(self.queue_download, self.queue_response,))
        self.send_process = multiprocessing.Process(target=self.handle_sending_process, args=(self.queue_upload,))
        self.trash_collecting_process = multiprocessing.Process(target=self.handle_trash_process)


        self.client = mqtt_client
        self.MQTT_TOPIC_DWNSTR = MQTT_TOPIC_DWNSTR
        self.MQTT_TOPIC_UPLSTR = MQTT_TOPIC_UPLSTR
        self.MQTT_TOPIC_DWNRES = MQTT_TOPIC_DWNRES
        self.MQTT_TOPIC_UPLREQ = MQTT_TOPIC_UPLREQ
        self.MQTT_TOPIC_DWNREQ = MQTT_TOPIC_DWNREQ


        self.downloading = False
        self.uploading = False
        self.download_progress = 0
        self.download_amount = 0
        self.uploaded_bytes = 0
        self.total_bytes = 0

        self.sending_bool = False
        self.moving_bool = False

        self.download_state = DownloadState.IDLE
        self.upload_state = UploadState.NO_UPLOAD
    def start_processes(self) -> None:
       # self.move_process.start()
       # self.send_process.start()
       # self.trash_collecting_process.start()
        
        self.monitor_processes(self.client)
    
    
    def handle_moving_process(self, queue_status: multiprocessing.Queue, queue_response: multiprocessing.Queue) -> None:
        while True:    
            self.downloading = False
            self.queue_status_download(DownloadState.IDLE, self.device_manager.moved_data, self.device_manager.drone_folder_size, queue_status)
            self.device_manager.listen_for_drone(queue_status, self.stop_signal_download)
            self.queue_status_download(DownloadState.BUSY, self.device_manager.moved_data, self.device_manager.drone_folder_size, queue_status)
            self.device_manager.move_data_from_drone(self.device_manager.dbox_index, self.device_manager.chunk_size, self.stop_signal_moving, queue_status)
            self.downloading = False
            dbox_index = str(self.device_manager.dbox_index)
            self.device_manager.unmount_drone()
            self.queue_status_download(DownloadState.IDLE, self.device_manager.moved_data, self.device_manager.drone_folder_size, queue_status)
            self.device_manager.rename_folders_drone(os.path.join(self.device_manager.output_folder_path, dbox_index), self.in_progress_word)
            if self.stop_signal_moving.is_set():
                print("Moving process halted, drone unmounted")
                self.queue_status_download(DownloadState.IDLE, self.device_manager.moved_data, self.device_manager.drone_folder_size, queue_status)
                self.stop_signal_moving.clear()
                break
            #self.device_manager.wait_for_disconnect_drone()
    def handle_sending_process(self, queue_status: multiprocessing.Queue) -> None:
        while True:
            print("Sending process started")
            dbox_index = str(self.device_manager.dbox_index)
            self.uploading = False
            subfolder_name_list = self.device_manager.get_folder_names_drone(dbox_index)
            self.azure_storage.uploaded_bytes = 0
            self.azure_storage.total_bytes = 0
            for subfolder_name in subfolder_name_list[:]:
                self.azure_storage.total_bytes += self.device_manager.get_folder_size(os.path.join(self.device_manager.output_folder_path, dbox_index, subfolder_name))
            for subfolder_name in subfolder_name_list[:]:
                if self.stop_signal_sending.is_set():
                    break
                if not (self.in_progress_word in subfolder_name):
                    continue
                self.uploading = True
                self.queue_status(UploadState.NO_UPLOAD, self.uploaded_bytes, self.total_bytes, queue_status)
                uploaded_files = self.azure_storage.send_data_drone(os.path.join(self.device_manager.output_folder_path, dbox_index), subfolder_name, self.device_manager.drone_device_name, self.container_name, self.in_progress_word, self.stop_signal_sending, queue_status, self.device_manager.time_interval)
                self.queue_status(UploadState.IN_PROGRESS, self.uploaded_bytes, self.total_bytes, queue_status)
                if not uploaded_files:
                    continue
                if not self.device_manager.rename_files_drone(subfolder_name, uploaded_files, self.in_progress_word):
                    new_folder_name = f"{subfolder_name}_{self.in_progress_word}"
                    self.device_manager.rename_files_drone(new_folder_name, uploaded_files, self.in_progress_word)
            if self.stop_signal_sending.is_set():
                self.queue_status(UploadState.PAUSED, self.uploaded_bytes, self.total_bytes, queue_status)
                break
            self.queue_status(UploadState.NO_UPLOAD, self.uploaded_bytes, self.total_bytes, queue_status)
            time.sleep(self.device_manager.time_interval)
        print("Sending process halted")
        self.stop_signal_sending.clear()
        exit(0)
    def queue_status(self, status: UploadState, progress: int, total: int, queue) -> None:
        data = (status, progress, total)
        queue.put(data)
    def queue_status_download(self, status: DownloadState, progress: int, total: int, queue) -> None:
        data = (status, progress, total)
        queue.put(data)
    def handle_trash_process(self) -> None:
        while not self.stop_signal_trash.is_set():
            subfolder_name_list = self.device_manager.get_folder_names_drone(self.device_manager.dbox_index)
            for subfolder_name in subfolder_name_list[:]:
                if self.stop_signal_trash.is_set():
                    break
                subfolder_path = os.path.join(self.device_manager.output_folder_path, self.device_manager.dbox_index, subfolder_name)
                try:
                    directory_files = os.listdir(subfolder_path)
                    for file in directory_files:
                        if self.stop_signal_trash.is_set():
                            break
                        if self.in_progress_word in file:
                            file_path = os.path.join(subfolder_path, file)
                            os.remove(file_path)
                except FileNotFoundError as e:
                    print(f"Error: {e}")
                    continue
                try:
                    if len(os.listdir(os.path.join(self.device_manager.output_folder_path, self.device_manager.dbox_index, subfolder_name))) == 0 and os.path.exists(os.path.join(self.device_manager.output_folder_path, subfolder_name)) and self.in_progress_word in subfolder_name:
                        print(f"Empty subfolder {subfolder_name}")
                        try :
                            os.rmdir(os.path.join(self.device_manager.output_folder_path, self.device_manager.dbox_index, subfolder_name))
                        except OSError as e:
                            print(f"Error, folder was not empty: {e}")
                            continue
                except FileNotFoundError as e:
                    print(f"Error: {e}")
                    continue
        print("Trash collecting process halted")
        self.stop_signal_trash.clear()
        exit(0)
    def stop_sending(self) -> None:
        self.stop_signal_sending.set()
        self.send_process.join()
        self.sending_bool = False
    def stop_moving(self) -> None:
        self.stop_signal_moving.set()
        self.stop_signal_download.set()
    def stop_trash(self) -> None:
        self.stop_signal_trash.set()
        self.trash_collecting_process.join()
    def start_trash(self) -> None:
        if self.trash_collecting_process.is_alive():
            time.sleep(10)
            if self.trash_collecting_process.is_alive():
                return
        self.trash_collecting_process = multiprocessing.Process(target=self.handle_trash_process)
        self.trash_collecting_process.start()
    def start_moving(self) -> None:
        self.stop_signal_download.clear()
        self.stop_signal_moving.clear()
        if self.move_process.is_alive():
            time.sleep(10)
            if self.move_process.is_alive():
                return
        self.move_process = multiprocessing.Process(target=self.handle_moving_process, args=(self.queue_download, self.queue_response,))
        self.move_process.start()
    def start_sending(self) -> None:
        if self.send_process.is_alive():
            time.sleep(10)
            if self.send_process.is_alive():
                return
        self.send_process = multiprocessing.Process(target=self.handle_sending_process, args=(self.queue_upload,))
        self.send_process.start()
        self.sending_bool = True
    def monitor_processes(self, client: mqtt.Client) -> None:
        while True:
            #download_amount // download_progress
            self.update_download_status()
            #uploaded_bytes // total_bytes
            self.update_upload_status()

            # Publish messages
            client.loop_start()
            self.make_download_stream_message(client)
            self.make_upload_stream_message(client)
            time.sleep(self.device_manager.time_interval)
            client.loop_stop()
            # Check if processes are alive
            if self.sending_bool == True and not self.send_process.is_alive():
                self.start_sending()
            if self.moving_bool == True and not self.move_process.is_alive():
                self.start_moving()
            if not self.trash_collecting_process.is_alive():
                self.start_trash()
    def update_download_status(self) -> None:
        while True:
            try:
                data = self.queue_download.get_nowait()
                if data is None:
                    break
                try:
                    self.download_state, self.download_progress, self.download_amount = data
                except ValueError as e:
                    print(f"Error: {e}")
                    continue
            except multiprocessing.queues.Empty:
                break
    def update_upload_status(self) -> None:
        while True:
            try:
                data = self.queue_upload.get_nowait()
                if data is None:
                    break
                try:
                    self.upload_state, self.uploaded_bytes, self.total_bytes = data
                except ValueError as e:
                    print(f"Error: {e}")
                    continue
            except multiprocessing.queues.Empty:
                break
    def make_download_stream_message(self, client) -> None:
        download_stream = DownloadStateStream()
        download_stream.progress = to_uint64(self.download_progress)
        if self.download_amount == 0:
            download_stream.total = to_uint64(0)
        else:
            download_stream.total = to_uint64(self.download_amount)
        download_stream.state = self.download_state
        serialized_download_response = download_stream.SerializeToString()
        client.publish(MQTT_TOPIC_DWNSTR, serialized_download_response)
    def make_upload_stream_message(self, client):
        cloud_upload_stream = CloudUploadStateStream()
        cloud_upload_stream.progress = to_uint64(self.uploaded_bytes)
        if self.total_bytes == 0:
            cloud_upload_stream.total = to_uint64(0)
        else:
            cloud_upload_stream.total = to_uint64(self.total_bytes)
        cloud_upload_stream.state = self.upload_state
        serialized_upload_response = cloud_upload_stream.SerializeToString()
        client.publish(self.MQTT_TOPIC_UPLSTR, serialized_upload_response)

def is_jpeg_by_filename(file_name: str) -> bool:
    lower_file_name = file_name.lower()
    return True
    #return lower_file_name.endswith('.jpg') or lower_file_name.endswith('.jpeg') or lower_file_name.endswith('.png')
def to_uint64(value):
    return value & ((1 << 64) - 1)

def on_connect(client, userdata, flags, rc):
    print("MQTT | Connected with result code "+str(rc))
    client.subscribe(MQTT_TOPIC_DWNREQ)
    client.subscribe(MQTT_TOPIC_UPLREQ)
    print("MQTT | Subscribed to topics")

def on_message(client, userdata, msg, process_handler: ProcessHandler):
    if msg.topic == MQTT_TOPIC_DWNREQ:
        download_request = DownloadAllowanceStream()
        download_request.ParseFromString(msg.payload)
        if download_request.allowance == DownloadAllowance.DL_ALLOWED:
            process_handler.start_moving()
            print("Received start moving")
            process_handler.moving_bool = True
        elif download_request.allowance == DownloadAllowance.DL_FORBIDDEN:
            process_handler.stop_moving()
            print("Received stop moving")
            process_handler.moving_bool = False
    elif msg.topic == MQTT_TOPIC_UPLREQ:
        upload_request = CloudUploadAllowanceStream()
        upload_request.ParseFromString(msg.payload)
        if upload_request.allowance == CloudUploadAllowance.CUA_FORBIDDEN:
            process_handler.stop_sending()
            print("Received stop sending")
            process_handler.sending_bool = False
        elif upload_request.allowance == CloudUploadAllowance.CUA_ALLOWED:
            process_handler.start_sending()
            print("Received start sending")
            process_handler.sending_bool = True
def on_message_wrapper(process_handler: ProcessHandler):
    def wrapper(client, userdata, msg):
        on_message(client, userdata, msg, process_handler)
    return wrapper
if __name__ == "__main__":
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = ConfigYAML(config_path)

    # Retrieve values
    input_device_name = config.get('device.inputDeviceName')
    container_name = config.get('azureStorage.containerName')
    storage_account_name = config.get('azureStorage.storageAccountName')
    azure_connection_file_name = config.get('azureStorage.azureConnectionFileNameYAML')
    #azure_connection_file_name = config.get('azureStorage.azureConnectionFileNameJSON')
    input_device_mount_point = config.get('device.inputDeviceMountPoint')
    delete_key_word = config.get('processing.deleteKeyWord')
    drone_vendor_id = config.get('drone.vendorID')
    image_folder_path = config.get('paths.imageFolderPath')
    output_folder_path = config.get('paths.outputFolderPath')
    time_interval = config.get('processing.timeInterval')
    upload_chunk_size = config.get('processing.uploadChunkSize')
    download_chunk_size = config.get('processing.downloadChunkSize')
    MQTT_PORT = config.get('mqtt.port')
    MQTT_TOPIC_DWNSTR = config.get('mqtt.topicDwnStr')
    MQTT_TOPIC_UPLSTR = config.get('mqtt.topicUplStr')
    MQTT_TOPIC_DWNRES = config.get('mqtt.topicDwnRes')
    MQTT_TOPIC_UPLREQ = config.get('mqtt.topicUplReq')
    MQTT_TOPIC_DWNREQ = config.get('mqtt.topicDwnReq')
    MQTT_BROKER = config.get('mqtt.broker')
    MQTT_CLIENT_NAME = config.get('mqtt.clientId')
    DBOX_INDEX = config.get('dbox.index')
    if None in [input_device_name, container_name, storage_account_name, azure_connection_file_name, input_device_mount_point, delete_key_word, drone_vendor_id, image_folder_path, output_folder_path, time_interval, upload_chunk_size, download_chunk_size, MQTT_PORT, MQTT_TOPIC_DWNSTR, MQTT_TOPIC_UPLSTR, MQTT_TOPIC_DWNRES, MQTT_TOPIC_UPLREQ, MQTT_TOPIC_DWNREQ, MQTT_BROKER, MQTT_CLIENT_NAME]:    
        print("Failed to retrieve values exiting program.")
        exit(1)
    try:
        mqtt_client = mqtt.Client(MQTT_CLIENT_NAME)
    except Exception as e:
        mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION1, MQTT_CLIENT_NAME)
    azure_storage = AzureStorage(storage_account_name, azure_connection_file_name, upload_chunk_size)
    if azure_storage.check_connection == False:
        print("Failed to connect to Azure")
        exit(1)
    device_manager = DeviceManager(input_device_name, input_device_mount_point, drone_vendor_id, image_folder_path, output_folder_path, time_interval, download_chunk_size, DBOX_INDEX)
    process_handler = ProcessHandler(azure_storage, device_manager, delete_key_word, container_name, mqtt_client, MQTT_TOPIC_DWNSTR, MQTT_TOPIC_UPLSTR, MQTT_TOPIC_DWNRES, MQTT_TOPIC_UPLREQ, MQTT_TOPIC_DWNREQ)
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message_wrapper(process_handler)
    if mqtt_client.connect(MQTT_BROKER, MQTT_PORT, 60) != 0:
        print("MQTT | Connection failed")
        exit(1)
    process_handler.start_processes()
    
