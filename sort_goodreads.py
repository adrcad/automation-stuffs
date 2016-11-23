# -*- coding: utf-8 -*-

import argparse
import os
from goodreads import client
from time import sleep
import sys
from kitchen.text.converters import getwriter, to_bytes, to_unicode
import locale


api_key = os.getenv("GR_API_KEY")
api_secret = os.getenv("GR_API_SECRET")


def parse_args():
    parser = argparse.ArgumentParser(description="Good reads classifier and help decision maker")
    parser.add_argument('--authenticate', '-a', dest='auth',
                        action='store_true',
                        help=("whether we should authenticate to goodreads server. "
                              "Not implemented yet !"),
                        required=False)

    parser.add_argument("-p", "--pages", metavar='NUM_PAGES', dest='pages',
                        help=("The maximum number of results pages to retrieve. All results by "
                              "default. Please enter an integer"),
                        required=False,
                        default='all')

    parser.add_argument("--only", "-o", metavar='PAGE', dest='only',
                        help=("Retrieve only this page. Page 1 by default"),
                        required=False)

    parser.add_argument("query", nargs='+',
                        help=("The query to perform. Enter something about the book you are "
                              "querying: the author name, the book title or a substring of the "
                              "book title or the field in which the book belongs. e.g: 'big data' "
                              "to find books relative to the subject"))

    return parser.parse_args()


def get_one_page(grc, args):
    try:
        pg = int(args.only)
    except ValueError:
        print("Invalid number of page. Please enter an integer value")
        return
    else:
        try:
            res = grc.search_books(args.query, page=pg)
        except TypeError:
            print("Inexistent result page")
            return
        except Exception as e:
            print("Got Unknown error: %s " % e)
            return
        else:
            print("Got page %s: \n%s" % (pg, "\n".join([to_unicode(b.title) for b in res])))
            print("-" * 56)
            return res


def pause_if_necessary(pg):
    sleep_time = 5
    if pg % 5 == 0:
        print("Sleeping %s seconds .... .... ...." % sleep_time)
        sleep(sleep_time)    # Pause for 5 seconds each 5 pages retrieval


def get_books(grc, args):
    if args.auth:
        print("Functionality not available at the moment")
        return
    if args.pages != 'all':
        try:
            pgs = int(args.pages)
        except ValueError:
            print("Invalid number of pages. Please enter an integer value")
            return
        else:
            if args.only:
                print("Can't request multiple pages and only a specific page at the same time. "
                      "We will give you the only page you need though (page %s)" % args.only)
                res = get_one_page(grc, args)
            else:
                res = []
                pg = 1
                while pg <= pgs:
                    pause_if_necessary(pg)
                    args.only = pg
                    res.extend(get_one_page(grc, args))
                    pg += 1

                return res
    else:
        if args.only:
            return get_one_page(grc, args)
        else:
            # TODO: try a parallellization of the page retrieval using threads or processes to speed
            # up the process
            res = []
            pg = 1
            while True:
                pause_if_necessary(pg)
                args.only = pg
                res.extend(get_one_page(grc, args))
                pg += 1
            print("Total pages retrieved: %s" % pg)
            return res


class Book(object):

    def __init__(self, lib_book, max_AR, max_NTR, max_TR, tTR=0.5, tAR=0.25, tNTR=0.25):
        super(Book, self).__init__()
        if lib_book.language_code == "en_US":
            self.lang = "English"
        elif lib_book.language_code == "fr_FR":
            self.lang = "Français"
        else:
            self.lang = "Not needed"
        self.pubDate = lib_book.publication_date
        self.ratingDist = {star_label: int(star_number)
                           for star_label, star_number in (tuple(rating.split(':'))
                                                           for rating in
                                                           lib_book.rating_dist.split('|'))}
        self.totalRating = float(self.ratingDist.pop('total', 'inf'))
        self.pages = lib_book.num_pages
        self.title = to_bytes(lib_book.title)   # Because we write it to a file
        self.averageRating = float(lib_book.average_rating)
        self.bookFormat = lib_book.format
        self.nbTextReviews = float(lib_book.text_reviews_count)
        self.tTR = tTR
        self.tAR = tAR
        self.tNTR = tNTR
        self.maxAR = max_AR
        self.maxNTR = max_NTR
        self.maxTR = max_TR
        self.fitnessScore = self.fitness()

    def fitness(self):    # Basic weighted fitness
        if self.maxNTR == 0:
            return 0
        return self.tTR * (self.totalRating / self.maxTR) + self.tAR * \
            (self.averageRating / self.maxAR) + self.tNTR * (self.nbTextReviews / self.maxNTR)

    def __str__(self):
        return self.title + " : " + str(self.fitnessScore * 100)


def sort_books(books):
    pass


def main():
    args = parse_args()

    # Setup stdout
    encoding = locale.getpreferredencoding()
    writer = getwriter(encoding)
    sys.stdout = writer(sys.stdout)

    args.query = to_unicode(args.query)

    goodreads_key = api_key
    goodreads_secret = api_secret

    grc = client.GoodreadsClient(goodreads_key, goodreads_secret)

    books = get_books(grc, args)
    AR_sorted = sorted(books, key=lambda b: float(b.average_rating))
    NTR_sorted = sorted(books, key=lambda b: float(b.text_reviews_count))
    max_AR = float(AR_sorted[-1].average_rating)
    max_NTR = float(NTR_sorted[-1].text_reviews_count)

    Books = []
    totaux = []
    for book in books:
        d = {star_label: int(star_number)
             for star_label, star_number in (tuple(rating.split(':'))
                                             for rating in
                                             book.rating_dist.split('|'))}
        totaux.append(float(d.pop('total', 'inf')))
    TR_sorted = sorted(totaux)
    max_TR = TR_sorted[-1]

    for book in books:
        b = Book(book, max_AR, max_NTR, max_TR)
        Books.append(b)

    if not os.path.isdir("results"):
        os.mkdir("results")
    result_file = os.path.join("results", "results.txt")
    with open(result_file, "w") as f:
        old, sys.stdout = sys.stdout, f
        print("List of results, sorted by higher fitness:\n<Book title> : <Book fitness>")
        print("-" * 56)
        for book in sorted(Books, key=lambda b: b.fitnessScore, reverse=True):
            print(book)
    sys.stdout = old    # restore stdout
    print("Find your results in the 'results.txt' file of the root directory of the script")

if __name__ == '__main__':
    main()
