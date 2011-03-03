#!/usr/bin/env python

import urllib2
import simplejson
import sys
from time import sleep
import csv
from dateutil.parser import parse as dateparse
import datetime

GITHUB_API = 'https://github.com/api/v2/json/%s'
GITHUB_ISSUES_LIST = "issues/list/%s/%s"
GITHUB_ISSUES_COMMENTS = "issues/comments/%s/%s"

def github_api_call(call):
    """
    Make a call to the Github API
    """
    try:
        return simplejson.loads(urllib2.urlopen(GITHUB_API % (call)).read())
    except urllib2.HTTPError as e:
        if e.code == 403:
            # hit the rate limit - wait 60 seconds then retry
            print >>sys.stderr, "Hit the rate limit, waiting 60 seconds..."
            sleep(60)
            return github_api_call(call)
        else:
            raise

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
        print "Fetched issues"
        for issue in data['issues']:
            issues[issue['number']] = {
                'title': issue['title'],
                'body': issue['body'],
                'created_at': dateparse(issue['created_at']),
                'state': issue['state'],
                'comments': []
            }
            
            print "Fetching comments for issue %d..." % issue['number']
            comments_data = github_api_call(
                    GITHUB_ISSUES_COMMENTS % (repository, issue['number']))
            for comment in comments_data['comments']:
                issues[issue['number']]['comments'].append({
                    'created_at': dateparse(comment['created_at']),
                    'body': comment['body'],
                })
    return issues

def write_jira_csv(fd, issues):
    # Get the most comments on an issue to decide how many comment columns we
    # need
    comments_columns = []
    for i in range(max(map(lambda issue: len(issue['comments']),
                           issues.values()))):
        comments_columns.append('Comments %d' % (i+1))
    issue_writer = csv.writer(fd)
    issue_writer.writerow(['ID', 'Title', 'Body', 'Created At', 'State'] +
        comments_columns)
    for id in issues:
        issue_writer.writerow([
            id,
            issues[id]['title'],
            issues[id]['body'],
            issues[id]['created_at'].strftime('%Y/%m/%d %H:%M'),
            issues[id]['state']] + 
            [comment['body'] for comment in issues[id]['comments']])

if __name__ == '__main__':
    with open(sys.argv[2], 'w') as fd:
        write_jira_csv(fd, load_github_issues(sys.argv[1]))