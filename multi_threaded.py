import os
import queue
import threading
import collections
import concurrent.futures
from github import Github


CommitInfo = collections.namedtuple('Info', ['username', 'additions', 'deletions', 'files'])

class GitRepoScraperMultiThreaded():

    def __init__(self, repo_name):
        access_token = os.environ.get('GIT_TOKEN')
        self._git_handle = Github(access_token)
        repo = self._git_handle.get_repo(repo_name)
        self._commits = repo.get_commits().reversed
        self.committers = dict()
        self.pipeline = queue.Queue()
        self.event = threading.Event()


    def collect_commit_data(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            executor.submit(self._producer)
            executor.submit(self._consumer)


    def print_results(self):
        for username, stats in sorted(
            self.committers.items(),
            reverse=True,
            key=lambda item: len(item[1]['files'])):

            print('*'*50)
            print(username)
            print(stats['files'])
            print(stats['additions'])
            print(stats['deletions'])
            print('-'*50)
            print()


    def _producer(self):
        for commit in self._commits:
            files = self._get_non_empty_files(commit.raw_data)
            if files:
                try:
                    username = commit.author.login
                except AttributeError:
                    username = commit.raw_data['commit']['author']['email']
                finally:
                    self.pipeline.put(CommitInfo(
                        username, 
                        commit.stats.additions, 
                        commit.stats.deletions,
                        files
                    ))

        self.event.set()

                
    def _consumer(self):
        while not self.event.is_set() or not self.pipeline.empty():
            commit_info = self.pipeline.get()
            username = commit_info.username
            if username not in self.committers:
                self.committers[username] = {
                    'additions': 0,
                    'deletions': 0,
                    'files': set()
                }
            self.committers[username]['additions'] += commit_info.additions
            self.committers[username]['deletions'] += commit_info.deletions
            self.committers[username]['files'].update(commit_info.files)


    def _get_non_empty_files(self, commit_data):
        files = [_f['filename'] for _f in commit_data['files'] if _f['additions'] or _f['deletions']]
        return files


if __name__ == '__main__':
    repo_name = os.environ.get('REPO')
    gr_scraper = GitRepoScraperMultiThreaded(repo_name)
    gr_scraper.collect_commit_data()
    gr_scraper.print_results()