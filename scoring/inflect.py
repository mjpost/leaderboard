#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""Scorer for the inflection assignmennt (HW5). Scores by accuracy against one of
inflect_data/dtest.form (development) or inflect_data/etest.form (post-deadline test).

"""

import os
import codecs
import datetime
from itertools import izip

reverse_order = False
deadline = datetime.datetime(2014, 04, 28, 23, 00)

class PerSentenceScoresInfer(ndb.Model):
    score = ndb.IntegerProperty(repeated=True)

def oracle():
    query_results = PerSentenceScores.query().fetch()
    return 0.0

def score(e_file, assignment_key, test=False):

    goldfile = '%s/inflect_data/%s' % (os.path.dirname(os.path.realpath(__file__)), 'etest.form' if test else 'dtest.form')

    total = 0
    right = 0
    for line, gold in izip(codecs.open(e_file, 'r', 'utf-8'), codecs.open(goldfile, 'r', 'utf-8')):
        compared = map(lambda x: x[0] == x[1], izip(line.split(), gold.split()))
        right += sum(compared)
        total += len(compared)

    return 1.0 * right / total, 100
    

