
from __future__ import print_function
import httplib2
import os

from apiclient import discovery, http
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage
from lxml import etree

try:
    import argparse, io
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

SCOPES = 'https://www.googleapis.com/auth/drive.readonly'

CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Photos Backup'

# Personal settings
YEARS_TO_PROCESS = [2014,2015,2016,2017]
FILES_DOWNLOADED = 0
MAX_FILES_TO_DOWNLOAD = 20
BACKUP_DIR = ''
USERS = []


def get_credentials(user):
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   "google-photos-backup-{0}.json".format(user))

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def get_service(user):
    credentials = get_credentials(user)
    http = credentials.authorize(httplib2.Http())
    return discovery.build('drive', 'v3', http=http)

def get_google_photos_folder_id():
    results = DRIVE_SERVICE.files().list(
        fields="files(id)",q="mimeType='application/vnd.google-apps.folder' and name='Google Photos'"
    ).execute()
    items = results.get('files',[])
    return items[0].get('id');

def get_year_folder_id(photosFolderId, year):
    query = "'{0}' in parents and mimeType='application/vnd.google-apps.folder' and name='{1}'".format(photosFolderId, year)
    results = DRIVE_SERVICE.files().list(
        fields="files(id)",q=query
    ).execute()
    items = results.get('files',[])
    if(len(items) == 0):
        return None
    else:
        return items[0].get('id');

def get_files_in_folder(folderId, nextPageToken, year):
    global FILES_DOWNLOADED
    query = "'{0}' in parents".format(folderId)
    listParams = {'fields':'nextPageToken, files(id,name)', 'q':query}
    if(nextPageToken is not None):
        listParams['pageToken'] = nextPageToken
    results = DRIVE_SERVICE.files().list(**listParams).execute()
    items = results.get('files',[])
    for item in items:
        get_file(item.get("id"), item.get("name"), year, user)
        if(FILES_DOWNLOADED == MAX_FILES_TO_DOWNLOAD):
            return
        print(item.get("name"))

    nextPageToken = results.get('nextPageToken')
    if(nextPageToken is not None):
        get_files_in_folder(folderId, nextPageToken, year)

def get_file(fileId, fileName, year, user):
    global FILES_DOWNLOADED
    filePath = BACKUP_DIR + "/" + user + "/" + str(year) + "/" + fileName
    if(not os.path.exists(filePath)):
        request = DRIVE_SERVICE.files().get_media(fileId=fileId)
        fh = io.FileIO(filePath + ".inprogress", mode='wb')
        downloader = http.MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print("Download {0}% (file {1} of max {2})".format(int(status.progress() * 100), (FILES_DOWNLOADED+1), MAX_FILES_TO_DOWNLOAD))
        fh.close()
        os.rename(filePath + ".inprogress", filePath)
        FILES_DOWNLOADED += 1

def makeLocalFolders(user):
    if(not os.path.isdir(BACKUP_DIR)):
        os.makedirs(BACKUP_DIR)

    for year in YEARS_TO_PROCESS:
        yearDir = BACKUP_DIR + "/" + user + "/" + str(year)
        if(not os.path.isdir(yearDir)):
            os.makedirs(yearDir)


def main(user):
    makeLocalFolders(user)
    photosFolderId = get_google_photos_folder_id()
    for year in YEARS_TO_PROCESS:
        if(FILES_DOWNLOADED >= MAX_FILES_TO_DOWNLOAD):
            break
        yearFolderId = get_year_folder_id(photosFolderId, year)
        if(yearFolderId is not None):
            get_files_in_folder(yearFolderId, None, year)
    print(str(FILES_DOWNLOADED) + ' Files downloaded')


def getAlbumDetails():
    albums = []
    credentials = get_credentials()
    h = httplib2.Http(".cache")
    credentials.authorize(h)
    resp, content = h.request("https://picasaweb.google.com/data/feed/api/user/default", "GET", headers={'GData-Version':'2'})
    root = etree.fromstring(content)

    for album in root.findall('{*}entry'):
        titleTag = album.find('{*}title')
        idTag = album.find('{*}id')
        albumDetail = [idTag.text, titleTag.text]
        albums.append(albumDetail)

    return albums

if __name__ == '__main__':
    for user in USERS:
        DRIVE_SERVICE = get_service(user)
        main(user)
