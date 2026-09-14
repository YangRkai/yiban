from vision import cv2
from cv2_enumerate_cameras import enumerate_cameras

def list_sources():
    return [(f'{device.name} [{device.index}]',device.index) for device in enumerate_cameras(cv2.CAP_DSHOW)]

def choose_default(items):
    return next((label for label,index in items if 'obs virtual camera' in label.lower()),'')
