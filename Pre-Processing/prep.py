import os
import argparse
import xml.etree.ElementTree as ET
import random
import math
from collections import Counter
from utils import semeval2014
from copy import copy, deepcopy

parser = argparse.ArgumentParser(description='Generate finetuning corpus for restaurants.')

parser.add_argument('--noconfl',
                    action='store_true',
                    default=False)

parser.add_argument('--istrain',
                    action='store_true',
                    default=False)

parser.add_argument("--files",
                    type=str,
                    nargs='+',
                    action="store")

parser.add_argument("--output_dir",
                    type=str,
                    action="store",
                    default="processed")



args = parser.parse_args()


def create_sentence_pairs(sents, aspect_term_sentiments):
    # create sentence_pairs

    all_sentiments = []
    sentence_pairs = []
    labels = []

    for ix, ats in enumerate(aspect_term_sentiments):
        s = sents[ix]
        for k, v in ats:
            all_sentiments.append(v)
            sentence_pairs.append((s, k))
            labels.append(v)
    counts = Counter(all_sentiments)

    return sentence_pairs, labels, counts


def print_dataset_stats(name, sents, sent_pairs, counts):

    print('Label Counts', counts.most_common())
    
    print('POS%', counts['POS'] / len(sent_pairs))
    print('NEG%', counts['NEG'] / len(sent_pairs))
    print('NEU%', counts['NEU'] / len(sent_pairs))
    print()


def export_dataset_to_xml(fn, sentence_pairs, labels):
    
    sentences_el = ET.Element('sentences')
    sentimap_reverse = {
        'POS': 'positive',
        'NEU': 'neutral',
        'NEG': 'negative',
        'CONF': 'conflict'
    }

    for ix, (sentence, aspectterm) in enumerate(sentence_pairs):
        sentiment = labels[ix]
        sentence_el = ET.SubElement(sentences_el, 'sentence')
        sentence_el.set('id', str(ix))
        text = ET.SubElement(sentence_el, 'text')
        text.text = str(sentence).strip()
        aspect_terms_el = ET.SubElement(sentence_el, 'aspectTerms')

        aspect_term_el = ET.SubElement(aspect_terms_el, 'aspectTerm')
        aspect_term_el.set('term', aspectterm)
        aspect_term_el.set('polarity', sentimap_reverse[sentiment])
        aspect_term_el.set('from', str('0'))
        aspect_term_el.set('to', str('0'))

    def indent(elem, level=0):
        i = "\n" + level * "  "
        j = "\n" + (level - 1) * "  "
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + "  "
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for subelem in elem:
                indent(subelem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = j
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = j
        return elem

    indent(sentences_el)
    
    mydata = ET.tostring(sentences_el)
    with open(fn, "wb") as f:
        f.write(mydata)
        f.close()




for fn in args.files:

    print(args.output_dir)
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)

    print(fn)
    
    sents_train, ats_train, idx2labels = semeval2014(fn, remove_conflicting=args.noconfl)
    sentence_pairs_train, labels_train, counts_train = create_sentence_pairs(sents_train, ats_train)

    if args.istrain:
        if len(args.files) == 1:
            print_dataset_stats('Train', sents_train, sentence_pairs_train, counts_train)
            export_dataset_to_xml(args.output_dir + '/train.xml', sentence_pairs_train, labels_train)
            

    else:

        if len(args.files) == 1:
            export_dataset_to_xml(args.output_dir + '/test.xml', sentence_pairs_train, labels_train)

