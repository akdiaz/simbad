#! /usr/bin/env python2

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals

from astropy import coordinates
from astroquery.simbad import Simbad
from bs4 import BeautifulSoup
import argparse
import astropy.units as u
import datetime
import functools
import re
import requests
import sys
import time

class throttle(object):
    """Decorator to prevents a function from being called more than once every
       time period. To create a function that cannot be called more than once
       a minute:

       @throttle(minutes=1)
       def my_fun():
         pass

       [Based on https://gist.github.com/ChrisTM/5834503]
     """

    def __init__(self, seconds=0, minutes=0, hours=0):
        self.throttle_period = datetime.timedelta(
            seconds=seconds, minutes=minutes, hours=hours)
        self.time_of_last_call = datetime.datetime.min

    def __call__(self, fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            while True:
                now = datetime.datetime.now()
                time_since_last_call = now - self.time_of_last_call
                if time_since_last_call >= self.throttle_period:
                    break
            try:
                return fn(*args, **kwargs)
            finally:
                self.time_of_last_call = now

        return wrapper


def parse_coordinates(line):
    """From e.g. '05 35 24.550 -05 06 59.00' to SkyCoord object."""
    return coordinates.SkyCoord(line, unit=(u.hourangle, u.deg))

def get_output_filename(input_coords, extension='.txt'):
    """Return a string such as 'J053524.550-050659.000.txt'."""

    fmt = '{:02}{:02}{:06.3f}'
    h, m, s = input_coords.ra.hms
    ra = fmt.format(int(h), int(m), s)
    separator = '+' if input_coords.dec >= 0 else '-'
    d, m, s = [abs(x) for x in input_coords.dec.dms]
    dec = fmt.format(int(d), int(m), s)
    return 'J{ra}{sep}{dec}{ext}'.format(
        ra=ra, sep=separator, dec=dec, ext=extension)


# SIMBAD suggests submitting no more than 6 queries per second; if
# we submit more than that, our IP may be temporarily blacklisted
# (http://simbad.u-strasbg.fr/simbad/sim-help?Page=sim-url)
@throttle(seconds=0.25)
def query_reference(bibcode):
    """From 1999AJ....118..983R to e.g. 'Reipurth99'."""

    result_table = Simbad.query_bibcode(bibcode)
    data = str(result_table[0]).strip().splitlines()

    # Ugly hack to accommodate Ana Karla's wishes.
    # Something like [
    #   'References',
    #   '---------------------------- ...',
    #   '1999AJ....118..983R = DOI 10.1086/300958  --  ?',
    #   'Astron. J., 118, 983-989 (1999)',
    #   'REIPURTH B., RODRIGUEZ L.F. and CHINI R.',
    #   'VLA detection of protostars in OMC-2/3.',
    #   'Flags: Table 1: <[RRC99] VLA NN> (Nos 1-14).',
    #   'Files: (abstract)']

    # Extract the surname of the first author
    authors_line = data[4]
    # split('-') to handle Spanish names such as 'MORALES-CALDERON', which
    # we want to transform into 'Morales-Calderon'.
    name = authors_line.split()[0]
    first_author = '-'.join(x.capitalize() for x in name.split('-'))
    year_line = data[3]
    year = re.findall('\((\d{4})\)', year_line)[0]
    year = year[-2:]  # From '1999' to just '99'
    return first_author + year


@throttle(seconds=0.25)
def get_object_types(identifier):
    """Yield all the object types and their references.

    This is a monstrous hack from hell, parsing Simbad's HTML code in order the
    extract the data and format it the way Ana Karla needs it. There is no way,
    apparently, to fetch this using Astroquery, and the ASCII output of Simbad
    (which would be much simpler to parse) doesn't list this info. Yields
    two-elements tuple, with each type and the list of references. We use curly
    braces to surround bibliographical references; e.g. {2012ApJ...753L..35B}
    """

    url = 'http://simbad.u-strasbg.fr/simbad/sim-id'
    payload = {
        'Ident': identifier,
        'NbIdent': 1,
        'Radius': 2,
        'Radius.unit': 'arcmin',
        'submit': 'submit+id'}

    r = requests.get(url, params=payload)
    soup = BeautifulSoup(r.text, "html5lib")
    # It seems to be the fourth table...
    table = soup.find_all('table')[3]
    references = table.find_all('tt', title=True)

    for r in references:
        type_object = r.previous_sibling.previous_sibling
        tt = type_object.contents[1]
        type_ = tt.contents[0].strip()
        title = ", ".join(r.get('title').split(","))
        if "Ref" in title:
            # There must be a link to the reference...
            href = r.find_all('a')[0].get('href')
            bibcode = href.split('?bibcode=')[-1]
            title = title.replace('Ref', '{{{}}}'.format(bibcode))

        yield type_, title


def query_coordinates(input_coords):

    customSimbad = Simbad()
    customSimbad.add_votable_fields('sptype', 'coo_wavelength', 'otype(V)', 'id')
    result = customSimbad.query_region(input_coords, radius="1m")

    # A dictionary with the queried fields.
    fields = dict()

    ra = result['RA'][0]
    dec = result['DEC'][0]
    actual_coords = coordinates.SkyCoord(ra, dec, unit=(u.hourangle, u.deg))
    fields['distance'] = round(actual_coords.separation(coords).arcsec, 2)
    fields['ra'], fields['dec'] = ra, dec

    identifier = fields['main_id'] = result['MAIN_ID'][0]
    fields['identifiers'] = result['ID'][0]
    fields['reference'] = result['COO_BIBCODE'][0]
    fields['spectral_type'] = result['SP_TYPE'][0]
    fields['wavelength'] = result['COO_WAVELENGTH'][0]
    fields['type'] = result['OTYPE_V'][0]
    fields['all_types'] = get_object_types(identifier)
    return fields


def generate_report(fields, output_filename):
    """Write the report of an object to a file."""

    with open(output_filename, 'wt') as fd:

        fd.write("Identifier: {}\n".format(fields['identifiers']))
        ra, dec, wavelength = fields['ra'], fields['dec'], fields['wavelength']
        author = query_reference(fields['reference'])
        if wavelength:
            wavelength = '({})'.format(wavelength)

        fd.write("\nCoordinates (ICRS): {} {} {} [{}]\n".format(ra, dec, author, fields['reference']))
        fd.write("\nDistance to center (arcsec): {}\n".format(fields['distance']))
        fd.write("\nType: {}\n".format(fields['type']))

        references = list(fields['all_types'])
        # Replace bibliographical references (which will look like the following:
        # {1999AJ....118..983R}, curly braces included, with the author + year;
        # e.g. 'Reipurth99'. We pass the function to re.sub(), which will call it
        # for every non-overlapping occurrence to get the replacement string.
        regexp = '{[\w.]+}'
        def bibcode_replacement(matchobj):
            # Remove surrounding curly braces.
            bibcode = matchobj.group(0).strip("{}")
            return query_reference(bibcode)

        fd.write("\nAll types: ")
        for index, (type_, refs) in enumerate(references):
            refs = re.sub(regexp, bibcode_replacement, refs)
            fd.write('{} ({})'.format(type_, refs))
            if index < len(references) - 1:
                fd.write(', ')
            else:
                fd.write('\n')

        fd.write("\nSpectral type: {}\n".format(fields['spectral_type']))

        fd.write("\nReferences:\n")
        url = 'http://simbad.u-strasbg.fr/simbad/sim-ref?bibcode={}'.format
        # First print the URL of the main bibliographical reference
        fd.write('{} {}\n'.format(fields['reference'], url(fields['reference'])))
        # Avoid duplicate references
        unique_references = set()

        # Now the URLs of the different references.
        for _, ref in references:
            for r in re.findall(regexp, ref):
                bibcode = r.strip("{}")
                unique_references.add('{} {}'.format(query_reference(bibcode), url(bibcode)))
        for r in sorted(unique_references):
            fd.write('{}\n'.format(r))


if __name__ == "__main__":

    parser = argparse.ArgumentParser(
        description='Query SIMBAD objects. See: '
        'https://docs.google.com/document/d/1GA3ZV6_DomkjaBFU3dsyVr3GHaVZdQcUXEBpbM07XBA/edit?usp=sharing')
    parser.add_argument('coordinates_file',
        metavar='FILE', type=argparse.FileType('r'), nargs=1,
        help='A file with the coordinates of each astronomical object, one '
             'per line, in the following format: hh mm ss.sss -gg mm ss.ss.')

    args = parser.parse_args()
    index = 1
    for line in args.coordinates_file[0]:
        line = line.strip()
        # Ignore empty lines and comments.
        if not line or line.startswith('#'):
            continue

        coords = parse_coordinates(line)
        fields = query_coordinates(coords)
        print('[{}] {}...'.format(index, line), end='')
        sys.stdout.flush()
        output_filename = get_output_filename(coords)
        generate_report(fields, output_filename)
        print(" saved to {}".format(output_filename))
        index += 1
