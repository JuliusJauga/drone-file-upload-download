# -*- coding: utf-8 -*-
# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: box_common_api.proto
"""Generated protocol buffer code."""
from google.protobuf.internal import builder as _builder
from google.protobuf import descriptor as _descriptor
from google.protobuf import descriptor_pool as _descriptor_pool
from google.protobuf import symbol_database as _symbol_database
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor_pool.Default().AddSerializedFile(b'\n\x14\x62ox_common_api.proto\x12\x0e\x62ox_common_api\"\xaa\x01\n\tStateInfo\x12\x38\n\x08progress\x18\x01 \x01(\x0e\x32&.box_common_api.StateInfo.ProcessState\x12\x11\n\terrorCode\x18\x02 \x01(\r\"P\n\x0cProcessState\x12\x08\n\x04NONE\x10\x00\x12\x0f\n\x0bIN_PROGRESS\x10\x01\x12\r\n\tCOMPLETED\x10\x02\x12\x0b\n\x07\x41\x42ORTED\x10\x03\x12\t\n\x05\x45RROR\x10\x04\"\x17\n\x15\x43ontrollerInfoRequest\"v\n\x16\x43ontrollerInfoResponse\x12\x17\n\x0fsoftwareVersion\x18\x01 \x01(\t\x12\x17\n\x0fswitcherVersion\x18\x02 \x01(\t\x12\x14\n\x0csoftwareType\x18\x03 \x01(\t\x12\x14\n\x0cserialNumber\x18\x04 \x01(\t\"E\n\x1a\x43ontrollerFlashModeRequest\x12\'\n\x04mode\x18\x01 \x01(\x0e\x32\x19.box_common_api.FlashMode\"O\n\x1b\x43ontrollerFlashModeResponse\x12\x30\n\x08response\x18\x01 \x01(\x0e\x32\x1e.box_common_api.ResponseStatus\"\x18\n\x16\x43ontrollerResetRequest\"K\n\x17\x43ontrollerResetResponse\x12\x30\n\x08response\x18\x01 \x01(\x0e\x32\x1e.box_common_api.ResponseStatus*/\n\tFlashMode\x12\x11\n\rPLACEHOLDER_1\x10\x00\x12\x06\n\x02ON\x10\x01\x12\x07\n\x03OFF\x10\x02*r\n\x0eResponseStatus\x12\x08\n\x04NONE\x10\x00\x12\x0c\n\x08\x41\x43\x43\x45PTED\x10\x01\x12\n\n\x06\x46\x41ILED\x10\x02\x12\x0c\n\x08REJECTED\x10\x03\x12\x17\n\x13\x41LREADY_IN_PROGRESS\x10\x04\x12\x15\n\x11\x41PI_NOT_SUPPORTED\x10\x05\x42\x1d\n\x19\x61pp.diab.box.apiv2.commonP\x01\x62\x06proto3')

_builder.BuildMessageAndEnumDescriptors(DESCRIPTOR, globals())
_builder.BuildTopDescriptorsAndMessages(DESCRIPTOR, 'box_common_api_pb2', globals())
if _descriptor._USE_C_DESCRIPTORS == False:

  DESCRIPTOR._options = None
  DESCRIPTOR._serialized_options = b'\n\031app.diab.box.apiv2.commonP\001'
  _FLASHMODE._serialized_start=613
  _FLASHMODE._serialized_end=660
  _RESPONSESTATUS._serialized_start=662
  _RESPONSESTATUS._serialized_end=776
  _STATEINFO._serialized_start=41
  _STATEINFO._serialized_end=211
  _STATEINFO_PROCESSSTATE._serialized_start=131
  _STATEINFO_PROCESSSTATE._serialized_end=211
  _CONTROLLERINFOREQUEST._serialized_start=213
  _CONTROLLERINFOREQUEST._serialized_end=236
  _CONTROLLERINFORESPONSE._serialized_start=238
  _CONTROLLERINFORESPONSE._serialized_end=356
  _CONTROLLERFLASHMODEREQUEST._serialized_start=358
  _CONTROLLERFLASHMODEREQUEST._serialized_end=427
  _CONTROLLERFLASHMODERESPONSE._serialized_start=429
  _CONTROLLERFLASHMODERESPONSE._serialized_end=508
  _CONTROLLERRESETREQUEST._serialized_start=510
  _CONTROLLERRESETREQUEST._serialized_end=534
  _CONTROLLERRESETRESPONSE._serialized_start=536
  _CONTROLLERRESETRESPONSE._serialized_end=611
# @@protoc_insertion_point(module_scope)
