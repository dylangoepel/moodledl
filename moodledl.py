import urllib.request
import bs4
import os
import regex
import sys

def pathescape(p):
    forbidden = "()/:"
    pp = p
    for f in forbidden:
        pp = pp.replace(f, "")
    return pp.strip().replace(" ", "_")

modregex = regex.compile("(https?://[^/]+)?/mod/([a-z]+)/view\.php\?id=([0-9]+)")
courseregex = regex.compile("(https?://[^/]+)?/course/view\.php\?id=([0-9]+)")
fileregex = regex.compile("(https?://[^/]+)?/pluginfile.php/[0-9]+/mod_resource/content/.*")

class MoodleRepo():
    def __init__(self, baseurl, session):
        self.baseurl = baseurl
        self.session = session
        self.courses = {0: {}}
        self.names = {}
        self.loadedCourses = [0]
        self.loadedResources = []

    def add_course(self, id):
        if id in self.courses:
            return
        self.courses[id] = {}

    def add_mod(self, courseid, kind, id, name):
        if courseid not in self.courses:
            self.add_course(courseid)
        if kind not in self.courses[courseid]:
            self.courses[courseid][kind] = []
        if id not in self.courses[courseid][kind]:
            self.courses[courseid][kind].append(int(id))
            self.names[id] = name

    def load_course(self, id):
        if id in self.loadedCourses or id == 0:
            return
        self.scrape(f"/course/view.php?id={id}")

    def scrape(self, url):
        nurl = url
        if url.startswith("/"):
            nurl = self.baseurl + url
        courseid = 0
        m = courseregex.match(url)
        if m:
            courseid = int(m.group(2))
        req = urllib.request.Request(nurl)
        req.add_header("Cookie", "MoodleSession=" + self.session)
        resp = urllib.request.urlopen(req)
        status = resp.getcode()
        if status != 200:
            print(f"[-] http error response {status}", file=sys.stderr)
            return []
        root = bs4.BeautifulSoup(resp.read(), features="lxml")
        for link in root.find_all("a"):
            m = modregex.match(link["href"])
            if m is not None:
                self.add_mod(courseid, m.group(2), int(m.group(3)), link.text)
            m = courseregex.match(link["href"])
            if m is not None:
                self.add_course(int(m.group(2)))
        if courseid != 0:
            title = root.find("h1")
            print(f"[+] found course '{title.text}'", file=sys.stderr)
            self.names[courseid] = title.text
        if courseid != 0:
            self.loadedCourses.append(courseid)

    def load_next_course(self):
        nextToLoad = None
        for c in self.courses:
            if c not in self.loadedCourses:
                nextToLoad = c
                break
        if nextToLoad is not None:
            self.load_course(nextToLoad)
            return True
        else:
            return False

    def load_all_courses(self):
        while self.load_next_course():
            pass

    def load_resource(self, resource, dir):
        if resource in self.loadedResources:
            return []
        req = urllib.request.Request(f"{self.baseurl}/mod/resource/view.php?id={resource}")
        req.add_header("Cookie", "MoodleSession=" + self.session)
        resp = urllib.request.urlopen(req)
        root = bs4.BeautifulSoup(resp.read(), features='lxml')
        for link in root.find_all("a"):
            if fileregex.match(link["href"]):
                path = dir + "/" + link["href"].split("/")[-1]
                print(f"[+] found resource '{path}'", file=sys.stderr)
                self.loadedResources.append(resource)
                return [(link["href"], path)]
        return []

    def download(self, url, path):
        if os.path.exists(path):
            return
        print(f"[+] downloading '{path}'...", file=sys.stderr)
        req = urllib.request.Request(url)
        req.add_header("Cookie", "MoodleSession=" + self.session)
        resp = urllib.request.urlopen(req)
        with open(path, "wb") as f:
            f.write(resp.read())

    def load_course_resources(self, course):
        if not course in self.names:
            print(f"[-] no name for course with id {course}.", file=sys.stderr)
            return []

        if course not in self.courses:
            print(f"[-] no data for {self.names[course]}.", file=sys.stderr)
            return []

        if 'resource' not in self.courses[course]:
            print(f"[-] no resources for {self.names[course]}", file=sys.stderr)
            return []

        coursePath = self.names[course]
        resources = []
        for resource in self.courses[course]['resource']:
            resources += self.load_resource(resource, coursePath)
        return resources

    def load_all_course_resources(self):
        resources = []
        for c in self.loadedCourses:
            if c != 0:
                resources += self.load_course_resources(c)
        return resources

repo = MoodleRepo(sys.argv[1].removesuffix("/"), sys.argv[2])
repo.scrape("/my/")
repo.load_all_courses()
for (url, path) in repo.load_all_course_resources():
    if not os.path.exists(os.path.dirname(path)):
        os.makedirs(os.path.dirname(path))
    repo.download(url, path)
