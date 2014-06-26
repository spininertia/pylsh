''' This module defines classes for generating LSH Signuture'''
import mmh3
import math
import numpy as np
from abc import abstractmethod
from bitarray import bitarray
from numpy.random import randn
from numpy.linalg import norm



class Lsh(object):
    ''' LSH implements locality sensitive hashing algorithm 
    that enables fast nearest neighbor search.

    Attributes:
        feat_dim: An integer indicating the dimension of feature vector
        sig_dim: An integer indicating the length of signature vector
        similarity_measure: An object indicating the similarity measure
    '''

    def __init__(self, feat_dim, sig_dim, similarity_measure, b=10):
        self.feat_dim = feat_dim
        self.sig_dim = sig_dim
        self.similarity_measure = similarity_measure
        self.hasher = self._init_hasher()
        self.banding_hashtable = BandingHashTable(sig_dim, b)

    def _init_hasher(self):
        '''initiate hasher function'''
        if isinstance(self.similarity_measure, JaccardSimilarity):
            return MinHasher(self.feat_dim, self.sig_dim)
        else:
            return RandomProjectionHasher(self.feat_dim, self.sig_dim)

    def generate_signature(self, lsh_object):
        '''generate signature for lsh_object'''
        lsh_object.signature = self.hasher.hash(lsh_object.feature)

    def index(self, lsh_object):
        '''Index an lsh_object'''
        self.generate_signature(lsh_object)
        self.banding_hashtable.put(lsh_object)

    def retrieve(self, lsh_object):
        '''Retrieve objects that are similar to lsh_object'''
        self.generate_signature(lsh_object)
        return self.banding_hashtable.get(lsh_object.signature)



class LshObject(object):
    ''' Defines an LSH object and methods to generate its signature '''

    identifier = 0

    def __init__(self, feature):
        LshObject.identifier += 1
        self.id = LshObject.identifier
        self.feature = feature
        self.signature = None

    def __eq__(self, other):
        if isinstance(other, LshObject):
            return self.id == other.id
        return NotImplemented

    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return "<%d %s>" % (self.id, self.feature)


class Hasher(object):
    '''Hasher is an abstract class which implements a family of hasher.

    Attributes:
        feat_dim: dimension of feature vector.
    ''' 

    def __init__(self, feat_dim, sig_dim):
        self.feat_dim = feat_dim
        self.sig_dim = sig_dim

    @abstractmethod
    def hash(self, feature):
        '''hash feature to generate signature'''
        pass

class MinHasher(Hasher): 
    '''MinHasher implements a family of hasher which generate signature 
    for jaccard similarity measure'''

    def hash(self, feature):
        return [self._hash(feature, k) for k in xrange(self.sig_dim)]

    @staticmethod
    def _hash(feature, k):
        '''generate hash for kth position'''
        hash_values = [mmh3.hash(str(pos), k) \
            for pos, val in enumerate(feature) if val == 1]

        # feature is a zero vector return a value that can never be hashed to
        if len(hash_values) == 0:
            return float("inf")
        else:
            return min(hash_values)

class RandomProjectionHasher(Hasher):
    '''RandomProjectionHasher generates random hyperplanes and make
    projections from features onto these planes to generate hash values.
    It's used together with cosine similarity measure'''

    def __init__(self, feat_dim, sig_dim):
        super(RandomProjectionHasher, self).__init__(feat_dim, sig_dim)
        self.planes = self._init_planes()
        
    def _init_planes(self):
        '''generates random planes'''
        return randn(self.sig_dim, self.feat_dim)

    def hash(self, feature):
        return bitarray([val > 0 for val in np.dot(self.planes, feature)])

class CosineSimilarity(object):
    '''CosineSimilarity implements the method 
    to compute similarity between two feature vector'''

    @staticmethod
    def compute_similarity(vec1, vec2):
        '''compute cosine similarity'''
        vec_len1 = norm(vec1)
        vec_len2 = norm(vec2)
        if vec_len1 == 0 or vec_len2 == 0:
            return 0
        else:
            return np.dot(vec1, vec2) / (norm(vec1) * norm(vec2))

    @staticmethod
    def approximate_similarity(sig1, sig2):
        '''
        compute the approximated cosine similarity for two signatures
        generated by applying RandomProjectionHasher
        '''
        return math.cos(math.pi * sum(sig1 ^ sig2) / len(sig1))

class JaccardSimilarity(object):
    '''JaccardSimilarity implements the method 
    to Jaccard similarity between two feature vector'''

    @staticmethod
    def compute_similarity(vec1, vec2):
        '''compute Jaccard similarity'''
        union = sum(np.bitwise_or(vec1, vec2))
        if union == 0:
            return 0.0
        else:
            return 1.0 * sum(np.bitwise_and(vec1, vec2)) / union

    @staticmethod
    def approximate_similarity(sig1, sig2):
        '''
        compute the approximated Jaccard similarity for two signatures
        generated by applying MinHasher
        '''
        return 1.0 * len([1 for x, y in zip(sig1, sig2) if x == y]) / len(sig1)

class BandingHashTable(object):
    '''Banding Hash Table implements a special hash table 
    which hashes similar object into the same bucket

    Attributes:
        r: number of rows per band
        b: number of bands (hash tables)
    '''

    def __init__(self, sig_dim, b):
        self.sig_dim = sig_dim
        self.b = b
        self.r = sig_dim / b
        self.hash_tables = self._init_hash_tables()

    def _init_hash_tables(self):
        '''Initialize self.b hash tables'''
        return [dict() for _ in xrange(self.b)]


    def put(self, lsh_object):
        '''Put an lsh_object into the BandingHashTable.'''
        bands = self._get_signature_segments(lsh_object.signature)
        for index, band in enumerate(bands):
            hash_result = hash(tuple(band))
            if hash_result not in self.hash_tables[index]:
                self.hash_tables[index][hash_result] = []
            self.hash_tables[index][hash_result].append(lsh_object)

    def get(self, signature):
        '''Get similar lsh_objects according to signature'''
        result = []
        bands = self._get_signature_segments(signature)
        for index, band in enumerate(bands):
            hash_result = hash(tuple(band))
            if hash_result in self.hash_tables[index]:
                result.extend(self.hash_tables[index][hash_result])

        return list(set(result))

    def _get_signature_segments(self, signature):
        '''Get segments of signature for every band. 
        For each band, there are at most r bits'''
        return [signature[self.r * i: self.r * (i + 1)] for i in xrange(self.b)]

