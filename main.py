import getpass
from abc import ABCMeta, abstractmethod, ABC
from builtins import list
from datetime import datetime

import redis
import json
import os
import typer


class GitLog:
    path: str = ""

    def __init__(self, path: str):
        self.path = path

    def get_path(self) -> str:
        return self.path

    def get_cmd(self) -> str:
        cd_cmd = "cd %s" % self.get_path()
        git_cmd = 'git log --pretty=format:"%h|%an|%ad|%s"  --date=format:"%Y-%m-%d %H:%I:%S"'
        return "%s && %s" % (cd_cmd, git_cmd)

    def log(self) -> list:
        cmd = os.popen(self.get_cmd())
        return cmd.read().splitlines()


class Log:
    version: str
    author: str
    date: str
    info: str
    log: str

    def __init__(self, log_data: str):
        self.log = log_data
        self.format_log()

    def format_log(self):
        arr: list = self.log.split('|')
        self.version = arr[0]
        self.author = arr[1]
        self.date = arr[2]
        self.info = arr[3]

    def get_version(self) -> str:
        return self.version

    def get_author(self) -> str:
        return self.author

    def get_date(self) -> str:
        return self.date

    def get_info(self) -> str:
        return self.info

    def get_log(self) -> dict:
        return {"version": self.version, "author": self.author, "date": self.date, "info": self.info}


class Record:
    deadline: str
    author: str
    status: bool
    record: dict
    title: str
    logs: list = []
    code: str

    def __init__(self, record_data: dict):
        self.record = record_data
        self.format_log()

    def format_log(self):
        self.deadline = self.record['deadline']
        self.author = self.record['author']
        self.title = self.record['title']
        self.code = self.record['code']

    def get_deadline(self) -> str:
        return self.deadline

    def get_author(self) -> str:
        return self.author

    def get_status(self) -> bool:
        return self.status

    def get_title(self) -> str:
        return self.title

    def get_code(self) -> str:
        return self.code

    def match_log(self, log_info: str) -> bool:
        find: bool = log_info.find(self.code) > -1
        if not find:
            find = log_info.find(self.title) > -1

        return find

    def get_logs(self) -> list:
        return self.logs

    def add_log(self, log_obj: Log):
        self.logs.append(log_obj)
        self.status = True

    def get_record(self) -> dict:
        return {"deadline": self.deadline, "author": self.author, "status": self.status, "title": self.title,
                "code": self.code}


class Manage:
    logs: list
    records: list

    def __init__(self, logs: list, records: list):
        self.logs = logs
        self.records = records

    def handle(self) -> list:
        for record in self.records:
            for log in self.logs:
                if record.match_log(log.get_info()):
                    record.add_log(log)
        return self.records


class OStream(metaclass=ABCMeta):
    @abstractmethod
    def get(self, id: str) -> dict:
        pass

    @abstractmethod
    def set(self, id: str, data: list) -> bool:
        pass

    @abstractmethod
    def delete(self, id: str) -> bool:
        pass

    @abstractmethod
    def all(self) -> list:
        pass


class Redis(OStream, ABC):
    redis: redis.Redis
    key: str

    def __init__(self):
        self.redis = redis.StrictRedis(host='localhost', port=6379, db=0)
        self.key = "redisManage:work:list"

    def get(self, id: str) -> dict:
        return json.loads(self.redis.hget(self.key, id))

    def set(self, id: str, data: dict) -> bool:
        return self.redis.hset(self.key, id, json.dumps(data))

    def delete(self, id: str) -> bool:
        return self.redis.hdel(self.key, id)

    def all(self) -> list:
        list = self.redis.hgetall(self.key)
        for item in list:
            list[item] = json.loads(list[item])
        return list


app = typer.Typer()


@app.command(name="list")
def list(path: str = ""):
    """
    List By Work Status
    """
    if len(path) == 0:
        path = os.path.split(os.path.realpath(__file__))[0]

    records = Redis().all()
    logs = GitLog(path).log()
    if len(logs) == 0:
        typer.echo("this path not as git repository")

    logList = []
    recordList = []
    for log in logs:
        logList.append(Log(log))
    for code in records:
        recordList.append(Record(records[code]))

    manage = Manage(logList, recordList)
    result = manage.handle()
    for record in result:
        print(record.get_record())


@app.command(name="set")
def set(
        code: str = typer.Option(..., prompt=True, help="Work Key, find to git log key"),
        title: str = typer.Option(...,
                                  prompt=True,
                                  help="Work Title, if cannot find key by log after will use title find"),
        author: str = typer.Option(getpass.getuser(), prompt=True, help="work author"),
        deadline: datetime = typer.Option(
            default=datetime.today().strftime("%Y-%m-%d %H:%M:%S"),
            prompt=True,
            formats=["%Y-%m-%d %H:%M:%S"],
            help="work deadline"
        ),
):
    """
    Create a new Work
    """
    redis = Redis()
    bool = redis.set(code, {
        "title": title,
        "code": code,
        "author": author,
        "deadline": deadline.strftime("%Y-%m-%d %H:%M:%S")
    })
    message_start = "add work: "
    if bool:
        ending = typer.style("??? Success", fg=typer.colors.GREEN)
    else:
        ending = typer.style("??? Fail: the work already exists (or not redis conn)", fg=typer.colors.RED)
    typer.echo(message_start + ending)

@app.callback()
def callback():
    """
    Manage work CLI app.

    Use it manage work
    """


if __name__ == '__main__':
    app()
