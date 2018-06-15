import time
import os
import sys
from os import path
import urllib.request
import bacli
import requests
from tqdm import tqdm
from requests.auth import HTTPBasicAuth

bacli.setDescription("Simple Github Scraper")


USERNAME = ""
PASSWORD = ""

REPO_SEARCH_URL = "http://api.github.com/search/repositories"
CODE_SEARCH_URL = "http://api.github.com/search/code"


def waitUntil(until):
    while True:
        waitTime = until - int(time.time()) + 1
        if waitTime <= 0:
            break
        print("Waiting {} seconds to resume.".format(waitTime))
        sleepTime = min(waitTime, 5)
        time.sleep(sleepTime)


def makeRequest(url, params=None, rawParams=None):
    auth = HTTPBasicAuth(USERNAME, PASSWORD)
    if rawParams:
        query = "?{}".format('&'.join("{}={}".format(k, v) for k, v in rawParams.items()))
        url = url + query

    # try again if fails
    while True:
        resp = requests.get(url, params=params, auth=auth)
        if resp.status_code == 200:
            return resp
        elif resp.status_code == 403:
            remaining = int(resp.headers.get("X-RateLimit-Remaining"))
            resetTime = int(resp.headers.get("X-RateLimit-Reset"))
            if remaining == 0:
                print("Rate limit reached.")
                waitUntil(resetTime)
                continue

        print("Invalid status code: {}".format(resp.status_code))
        print(resp.text)
        raise RuntimeError("Invalid request")


class Github(object):
    def __init__(self):
        pass

    class iterator(object):
        def __init__(self, response):
            self.response = response
            self.itemCount = int(self.data.get("total_count"))

        @property
        def data(self):
            return self.response.json()

        def getNextUrl(self):
            next = self.response.links.get("next")
            if not next:
                raise StopIteration
            return next["url"]

        def iterPages(self):
            yield self.data
            while True:
                self.response = makeRequest(self.getNextUrl())
                yield self.data

        def __iter__(self):
            for page in self.iterPages():
                items = page.get("items", list())
                for item in items:
                    yield item

        def __len__(self):
            return self.itemCount

    def findRepos(self, queryWord):
        params = {
            'q': queryWord
        }

        response = makeRequest(REPO_SEARCH_URL, params=params)
        return Github.iterator(response)

    def findFiles(self, repoName, queryString="", extensions=None):
        queryParams = list()
        queryParams.append("repo:{}".format(repoName))
        if extensions:
            for extension in extensions:
                queryParams.append("extension:{}".format(extension))
        queryParams.append(queryString)

        params = {
            'q': '+'.join(queryParams)
        }
        response = makeRequest(CODE_SEARCH_URL, rawParams=params)
        return Github.iterator(response)


def hashFilename(filePath):
    h = hash(filePath)
    return str(h + sys.maxsize + 1) + ".xml"


def getDownloadUrl(infoUrl):
    resp = makeRequest(infoUrl)
    data = resp.json()
    return data.get("download_url")


def downloadFile(url, downloadPath):
    os.makedirs(os.path.dirname(downloadPath), exist_ok=True)
    urllib.request.urlretrieve(url, downloadPath)


REPO_SEARCH_TERM = "petri"
CODE_SEARCH_TERM = "<pnml>"
EXTENSIONS = ["pnml", "xml"]


@bacli.command
def run(output="output"):
    """ Run the scraper """
    os.makedirs(output, exist_ok=True)
    g = Github()
    reposIt = tqdm(g.findRepos(REPO_SEARCH_TERM))
    reposIt.set_description("Repositories")
    for repo in reposIt:
        repoName = repo.get("full_name")
        if repoName:
            outputPath = path.join(output, repoName.replace('/', '-'))

            files = g.findFiles(repoName, queryString=CODE_SEARCH_TERM, extensions=EXTENSIONS)
            fileIt = tqdm(files)
            fileIt.set_description(repoName)
            for file in fileIt:
                infoUrl = file.get("url")
                downloadUrl = getDownloadUrl(infoUrl)
                filePath = hashFilename(file.get("path"))
                downloadPath = path.join(outputPath, filePath)
                downloadFile(downloadUrl, downloadPath)


