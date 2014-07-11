#!/usr/bin/env python
import datetime
import logging
import optparse
import os
import math
from collections import Counter

## Assignment info ##############################################
#
# All four values must be defined

# The assignment's name
name = 'Rerank'

# Set to true if lowest scores are best
scoring_method = 'BLEU'

# Set to true if highest scores are best
reverse_order = True

# The deadline YYYY, MM, DD, HH, MM (24 hour format)
deadline = datetime.datetime(2014, 04, 14, 23, 00)

#################################################################

def oracle():
  return 40.0571481713

# Collect BLEU-relevant statistics for a single hypothesis/reference pair.
# Return value is a generator yielding:
# (c, r, numerator1, denominator1, ... numerator4, denominator4)
# Summing the columns across calls to this function on an entire corpus will
# produce a vector of statistics that can be used to compute BLEU (below)
def bleu_stats(hypothesis, reference):
  yield len(hypothesis)
  yield len(reference)
  for n in xrange(1,5):
    s_ngrams = Counter([tuple(hypothesis[i:i+n]) for i in xrange(len(hypothesis)+1-n)])
    r_ngrams = Counter([tuple(reference[i:i+n]) for i in xrange(len(reference)+1-n)])
    yield max([sum((s_ngrams & r_ngrams).values()), 0])
    yield max([len(hypothesis)+1-n, 0])

# Compute BLEU from collected statistics obtained by call(s) to bleu_stats
def bleu(stats):
  if len(filter(lambda x: x==0, stats)) > 0:
    return 0
  (c, r) = stats[:2]
  log_bleu_prec = sum([math.log(float(x)/y) for x,y in zip(stats[2::2],stats[3::2])]) / 4.
  return math.exp(min([0, 1-float(r)/c]) + log_bleu_prec)

def score(e_file, assignment_key, test=False):
  hyp = [tuple(line.strip().split()) for line in e_file.strip().split('\n')]
  if len(hyp) != 800:
    return 0.0
  answerset = 'test' if test else 'dev'
  answerfile = '%s/rerank_data/%s.ref' % (os.path.dirname(os.path.realpath(__file__)),answerset)
  ref = [tuple(line.strip().split()) for line in open(answerfile)]
  if test:
    hyp = hyp[400:]
  else:
    hyp = hyp[:400]

  stats = [0 for i in xrange(10)]
  for (r,h) in zip(ref, hyp):
    stats = [sum(scores) for scores in zip(stats, bleu_stats(h,r))]
  return (100*bleu(stats), 100)

