import optparse
import logging
import sys
import os
import math
import datetime
import itertools
from collections import namedtuple, defaultdict

from google.appengine.ext import ndb
from google.appengine.api import taskqueue

reverse_order = True
deadline = datetime.datetime(2014, 03, 05, 23, 00)

# A translation model is a dictionary where keys are tuples of French words
# and values are lists of (english, logprob) named tuples. For instance,
# the French phrase "que se est" has two translations, represented like so:
# tm[('que', 'se', 'est')] = [
#   phrase(english='what has', logprob=-0.301030009985), 
#   phrase(english='what has been', logprob=-0.301030009985)]
# k is a pruning parameter: only the top k translations are kept for each f.
def all_phrases(sentence):
  for i in xrange(len(sentence)):
    for j in xrange(i+1, len(sentence)+1):
      yield tuple(sentence[i:j])

Phrase = namedtuple("phrase", "english, logprob")
def TM(filename, k, bitext):
  logging.info("Reading translation model from %s...\n" % (filename,))
  tm = {}
  f_phrases = set()
  e_phrases = set()
  for f, e in bitext: # limit mem use by keeping only useful entries
    f_phrases |= set(all_phrases(f))
    e_phrases |= set(all_phrases(e))
  for line in open(filename).readlines():
    (f, e, logprob) = line.strip().split(" ||| ")
    f_phr = tuple(f.split())
    e_phr = tuple(e.split())
    if f_phr in f_phrases and e_phr in e_phrases:
      tm.setdefault(f_phr, []).append(Phrase(e_phr, float(logprob)))
  for f in tm: # prune all but top k translations
    tm[f].sort(key=lambda x: -x.logprob)
    del tm[f][k:] 
  logging.info("Retained %d tm entries\n" % (len(tm),))
  return tm

# # A language model scores sequences of English words, and must account
# # for both beginning and end of each sequence. Example API usage:
# lm = LM(filename)
# sentence = "This is a test ."
# lm_state = lm.begin() # initial state is always <s>
# logprob = 0.0
# for word in sentence.split():
#   (lm_state, word_logprob) = lm.score(lm_state, word)
#   logprob += word_logprob
# logprob += lm.end(lm_state) # transition to </s>, can also use lm.score(lm_state, "</s>")[1]
ngram_stats = namedtuple("ngram_stats", "logprob, backoff")
class LM:
  def __init__(self, filename, tm):
    logging.info("Reading language model from %s...\n" % (filename,))
    self.table = {}
    e_words = set(['<s>', '</s>', '<unk>'])
    for entry in tm.itervalues(): # limit mem use by keeping ony useful entries
      for translation in entry:
        for word in translation.english:
          e_words.add(word)
    for line in open(filename):
      entry = line.strip().split("\t")
      if len(entry) > 1 and entry[0] != "ngram":
        (logprob, ngram, backoff) = (float(entry[0]), tuple(entry[1].split()), float(entry[2] if len(entry)==3 else 0.0))
        if all(word in e_words for word in ngram):
          self.table[ngram] = ngram_stats(logprob, backoff)
    logging.info("Retained %d lm entries\n" % (len(self.table),))

  def begin(self):
    return ("<s>",)

  def score(self, state, word):
    ngram = state + (word,)
    score = 0.0
    while len(ngram)> 0:
      if ngram in self.table:
        return (ngram[-2:], score + self.table[ngram].logprob)
      else: #backoff
        score += self.table[ngram[:-1]].backoff if len(ngram) > 1 else 0.0 
        ngram = ngram[1:]
    return ((), score + self.table[("<unk>",)].logprob)
    
  def end(self, state):
    return self.score(state, "</s>")[1]

# Three little utility functions:
def bitmap(sequence):
  """ Generate a coverage bitmap for a sequence of indexes """
  return reduce(lambda x,y: x|y, map(lambda i: long('1'+'0'*i,2), sequence), 0)

def bitmap2str(b, n, on='o', off='.'):
  """ Generate a length-n string representation of bitmap b """
  return '' if n==0 else (on if b&1==1 else off) + bitmap2str(b>>1, n-1, on, off)

def logadd10(x,y):
  """ Addition in logspace (base 10): if x=log(a) and y=log(b), returns log(a+b) """
  return x + math.log10(1 + pow(10,y-x))


def sentence_logprob(f, e, tm, lm):
  lm_state = lm.begin()
  lm_logprob = 0.0
  for word in e + ("</s>",):
    (lm_state, word_logprob) = lm.score(lm_state, word)
    lm_logprob += word_logprob
  
  alignments = [[] for _ in e]
  for fi in xrange(len(f)):
    for fj in xrange(fi+1,len(f)+1):
      if f[fi:fj] in tm:
        for phrase in tm[f[fi:fj]]:
          ephrase = phrase.english
          for ei in xrange(len(e)+1-len(ephrase)):
            ej = ei+len(ephrase)
            if ephrase == e[ei:ej]:
              alignments[ei].append((ej, phrase.logprob, fi, fj))

  # Compute sum of probability of all possible alignments by dynamic programming.
  # To do this, recursively compute the sum over all possible alignments for each
  # each pair of English prefix (indexed by ei) and French coverage (indexed by 
  # bitmap v), working upwards from the base case (ei=0, v=0) [i.e. forward chaining]. 
  # The final sum is the one obtained for the pair (ei=len(e), v=range(len(f))
  chart = [{} for _ in e] + [{}]
  chart[0][0] = 0.0
  for ei, sums in enumerate(chart[:-1]):
    for v in sums:
      for ej, logprob, fi, fj in alignments[ei]:
        if bitmap(range(fi,fj)) & v == 0:
          new_v = bitmap(range(fi,fj)) | v
          if new_v in chart[ej]:
            chart[ej][new_v] = logadd10(chart[ej][new_v], sums[v]+logprob)
          else:
            chart[ej][new_v] = sums[v]+logprob
  goal = bitmap(range(len(f)))
  if goal in chart[len(e)]:
    return lm_logprob + chart[len(e)][goal]
  else:
    return float('-inf')


class ModelScore(ndb.Model):
  assignment = ndb.KeyProperty()
  score = ndb.FloatProperty()
  chunk = ndb.IntegerProperty()


CHUNK_SIZE = 1
MAGIC_NUMBER = 12345
TIMEOUT_MINUTES = 10

def queued_score(data, assignment_key):
  chunk = int(data)
  a = assignment_key.get()
  english_data = a.filedata
  english = [tuple(line.strip().split()) for line in english_data.strip().split("\n")]
  if chunk == MAGIC_NUMBER:
    # check for completed scores and update percent_complete
    logging.info("Checking for completion of %s\n" % a.filename)
    mscores = ModelScore.query(ModelScore.assignment == assignment_key).fetch()
    num_scores = len(mscores)*CHUNK_SIZE
    logging.info("Found scores for %d sentences out of %d\n" % (num_scores, len(english)))
    if num_scores < len(english):
      # if scores are not done, resubmit this task if inside timeout limit
      earliest_time = datetime.datetime.now() - datetime.timedelta(minutes=TIMEOUT_MINUTES)
      if a.timestamp > earliest_time:
        taskqueue.add(url='/queued_score', 
                      params={'number': 2, # ugh
                              'key' : assignment_key.urlsafe(),
                              'data' : MAGIC_NUMBER,
                      },
                      countdown=20,
                      )
        a.percent_complete = 100 * num_scores / len(english)
      else: # otherwise give up
        a.percent_complete = 100
        a.score = float("-inf")
    else: # found all scores
      a.percent_complete = 100
      a.score = sum([m.score for m in mscores])
    a.put()

  else:
    chunk_start = chunk*CHUNK_SIZE
    chunk_end = (chunk+1)*CHUNK_SIZE
  
    french_file = '%s/decoding_data/input' % os.path.dirname(os.path.realpath(__file__))
    french = [tuple(line.strip().split()) for line in open(french_file).readlines()]
    bitext = [(f, e) for (f, e) in zip(french, english)[chunk_start:chunk_end]]

    tm_file = '%s/decoding_data/tm' % os.path.dirname(os.path.realpath(__file__))
    tm = TM(tm_file, sys.maxint, bitext)
    # tm should translate unknown words as-is with probability 1
    for word in set(sum(french,())):
      phr = (word,)
      if phr not in tm:
        tm[phr] = [Phrase(phr, 0.0)]
 
    lm_file = '%s/decoding_data/lm' % os.path.dirname(os.path.realpath(__file__))
    lm = LM(lm_file, tm)
   
    total_logprob = 0.0
    for f, e in bitext:
      total_logprob += sentence_logprob(f,e, tm, lm)
  
    logging.info("Scored file %s, segments %d-%d, result=%.2f\n" % (a.filename, chunk_start, chunk_end-1, total_logprob))
    model_score = ModelScore(assignment = assignment_key,
                             chunk = chunk,
                             score = total_logprob)
    model_score.put()
    mscores = ModelScore.query(ModelScore.assignment == assignment_key).fetch()
    num_scores = len(mscores)*CHUNK_SIZE
    a.percent_complete = 100 * num_scores / len(english)
    a.put()
 

def oracle():
  mscores = ModelScore.query().fetch() 
  best_score = defaultdict(lambda: float('-inf'))
  for mscore in mscores:
    best_score[mscore.chunk] = max([best_score[mscore.chunk], mscore.score])
  return sum(best_score.itervalues())


def score(english_data, assignment_key, test=False):
  if not test:
    # sanity check data: if wrong length, don't even try to score
    french_file = '%s/decoding_data/input' % os.path.dirname(os.path.realpath(__file__))
    french = [line for line in open(french_file).readlines()]
    english = [line for line in english_data.strip().split("\n")]
    if len(english) != len(french):
      logging.warning("len(e) = %d, len(f) = %d" % (len(english), len(french)))
      return (float("-inf"), 100)
    else:
      for i in range(len(english)/CHUNK_SIZE) + [MAGIC_NUMBER]:
        taskqueue.add(url='/queued_score', 
                      params={'number': 2, # ugh
                              'key' : assignment_key.urlsafe(),
                              'data' : i
                      })
      return (float("-inf"), 0)
  else:
    return (float("-inf"), 100)
