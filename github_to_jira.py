#!/usr/bin/env python

import base64
import collections
import csv
import itertools as it
import os
import sys
from time import sleep
import urllib2

from dateutil.parser import parse as dateparse
import simplejson

GITHUB_API = 'https://github.com/api/v2/json/%s'
GITHUB_ISSUES_LIST = "issues/list/%s/%s"
GITHUB_ISSUES_COMMENTS = "issues/comments/%s/%s"

def github_open_api(call,
                   username=os.getenv('GITHUB_USERNAME'),
                   password=os.getenv('GITHUB_PASSWORD')):
    request = urllib2.Request(GITHUB_API % (call,))
    if username:
        auth = base64.encodestring(':'.join((username, password))).strip('\n')
        request.add_header('Authorization', 'Basic ' + auth)
    return urllib2.urlopen(request)

def github_api_call(call):
    """
    Make a call to the Github API
    """
    try:
        return simplejson.load(github_open_api(call))
    except urllib2.HTTPError as e:
        if e.code == 403:
            # hit the rate limit - wait 60 seconds then retry
            print >>sys.stderr, "Hit the rate limit, waiting 60 seconds..."
            sleep(60)
            return github_api_call(call)
        else:
            raise

def get_num_comments(issue):
    return issue['comments']

def get_num_labels(issue):
    return len(issue['labels'])

def get_comments(repository, issue):
    """
    Get a list of all the comments for this issue as dictionaries.
    """
    print "Fetching comments for issue %d..." % issue['number']
    comments = []
    data = github_api_call(GITHUB_ISSUES_COMMENTS %
                                               (repository, issue['number']))
    for comment in data['comments']:
        comments.append({
            'created_at': dateparse(comment['created_at']),
            'body': comment['body'],
        })
    return comments

def get_labels(repository, issue):
    """
    Get a list of all the labels associated with this issue.
    """
    return issue['labels']

def load_github_issues(repository):
    """
    Get all the issues associated with a Github repository as a dictionary of
    issues, where the key is the issue ID and the value is a dictionary of the
    issue keys: created_at, state, title, body, comments, which is a list of
    dictionaries with keys: created_at and body
    """
    issues = {}
    for state in ('open', 'closed'):
        data = github_api_call(GITHUB_ISSUES_LIST % (repository, state))
        print "Fetched %s issues" % state
        for issue in data['issues']:
            issue['created_at'] = dateparse(issue['created_at'])
            issues[issue['number']] = issue
    return issues

def ensure_encoded(obj, encoding='us-ascii'):
    """
    If a string is unicode return its encoded version, otherwise return it raw.
    """
    if isinstance(obj, unicode):
        return obj.encode(encoding)
    else:
        return obj

def pad_list(l, size, obj):
    """
    Pad a list to given size by appending the object repeatedly as necessary.
    Cuts off the end of the list if it is longer than the supplied size.

    >>> pad_list(range(4), 6, 'x')
    [0, 1, 2, 3, 'x', 'x']
    >>> pad_list(range(4), 2, 'x')
    [0, 1]
    >>> pad_list(range(4), 4, 'x')
    [0, 1, 2, 3]

    """
    return list(it.islice(it.chain(l, it.repeat(obj)), size))

def write_jira_csv(fd, repository):
    # Get the most comments on an issue to decide how many comment columns we
    # need
    issues = load_github_issues(repository).values()
    issue_writer = csv.writer(fd)
    max_num_labels = max(map(get_num_labels, issues))
    max_num_comments = max(map(get_num_comments, issues))
    label_headers = ['Labels %d' % (i+1) for i in xrange(max_num_labels)]
    comment_headers = ['Comments %d' % (i+1) for i in xrange(max_num_comments)]
    headers = ['ID', 'Title', 'Body', 'Created At', 'State']
    headers += label_headers
    headers += comment_headers
    issue_writer.writerow(headers)
    known_attr_parsers = dict(
            created_at=lambda x: x.strftime('%Y/%m/%d %H:%M'))
    all_attr_parsers = collections.defaultdict(lambda: lambda x: x,
                                               known_attr_parsers)
    for issue in issues:
        attrs = ['number', 'title', 'body', 'created_at', 'state']
        row = [all_attr_parsers[attr](issue[attr]) for attr in attrs]
        row += pad_list(get_labels(repository, issue), max_num_labels, '')
        row += [comment['body'] for comment in get_comments(repository, issue)]
        # As per http://docs.python.org/library/csv.html
        row = [ensure_encoded(e, 'utf-8') for e in row]
        issue_writer.writerow(row)

if __name__ == '__main__':
    with open(sys.argv[2], 'w') as fd:
        write_jira_csv(fd, sys.argv[1])
