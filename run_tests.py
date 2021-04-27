#! /usr/bin/env python






import unittest

from simbad_batch import (
    parse_coordinates,
    query_reference,
    get_object_types,
    get_output_filename,
)

class TestParseCoordinates(unittest.TestCase):

    def test_parse_coordinates(self):

        # One of the examples provided by Ana Karla...
        vla7 = "05 35 24.550 -05 06 59.00"
        coords = parse_coordinates(vla7)

        h, m, s = coords.ra.hms
        self.assertEqual(h, 5)
        self.assertEqual(m, 35)
        self.assertAlmostEqual(s, 24.55)

        d, m, s = coords.dec.dms
        self.assertEqual(d, -5)
        self.assertEqual(m, -6)
        self.assertAlmostEqual(s, -59)

        # ... and my favorite astronomical object.
        trumpler37 = "21 39 00.0 +57 29 24"
        coords = parse_coordinates(trumpler37)

        h, m, s = coords.ra.hms
        self.assertEqual(h, 21)
        self.assertEqual(m, 39)
        self.assertAlmostEqual(s, 0)

        d, m, s = coords.dec.dms
        self.assertEqual(d, 57)
        self.assertEqual(m, 29)
        self.assertAlmostEqual(s, 24)


class TestGetOutputFilename(unittest.TestCase):

    def test_get_output_filename_VLA(self):
        vla7 = '05 35 24.550 -05 06 59.00'
        expected = 'J053524.550-050659.000.txt'
        coords = parse_coordinates(vla7)
        self.assertEqual(get_output_filename(coords), expected)

    def test_get_output_filename_HOPS(self):
        hops370 = '05 35 27.63370 -05 09 34.3737'
        expected = 'J053527.634-050934.374.txt'
        coords = parse_coordinates(hops370)
        self.assertEqual(get_output_filename(coords), expected)

    def test_get_output_filename_Trumpler37(self):
        trumpler37 = '21 39 00.0 +57 29 24'
        expected = 'J213900.000+572924.000.txt'
        coords = parse_coordinates(trumpler37)
        self.assertEqual(get_output_filename(coords), expected)


class TestQueryReference(unittest.TestCase):

    # Proper unit tests don't talk to remote services, but meh.
    def test_query_reference(self):
        references = {
            '1999AJ....118..983R': 'Reipurth99',
            '2012ApJ...753L..35B': 'Billot12',
            '2011ApJ...726...46N': 'Nakamura11',
            '2005A&A...432..161G': 'Goddi05',
            '2016A&A...588A..30S': 'Sadavoy16',
            '2013ApJS..209...25K': 'Kang13',
            '2011ApJ...726...46N': 'Nakamura11',
            '2011ApJ...733...50M': 'Morales-Calderon11',
            '2010ApJS..186..406D': 'Dotson10',
            '1989MNRAS.241..469R': 'Rayner89',
            '2003yCat.2246....0C': 'Cutri03',
            }

        print()
        for bibcode, expected in references.items():
            output = query_reference(bibcode)
            print('{} -> {}'.format(bibcode, output))
            self.assertEqual(output, expected)


class TestGetObjectTypes(unittest.TestCase):

    def test_get_object_types_VLA(self):
        identifier = '[RRC99] VLA 7'
        types = dict(get_object_types(identifier))
        self.assertEqual(1, len(types))
        self.assertEqual(types['Rad'], '[RRC99]')

    def test_get_object_types_2MASS(self):
        identifier = '2MASS J05352762-0509337'
        types = dict(get_object_types(identifier))
        self.assertEqual(8, len(types))
        self.assertEqual(types['*'], '')
        self.assertEqual(types['Y*O'], '{2012ApJ...753L..35B}, HOPS, HOY, ISOY, [MGM2012]')
        self.assertEqual(types['IR'], '2MASS, TKK, [GBM74], [MWZ90], [NCM2003]')
        self.assertEqual(types['smm'], '{2007MNRAS.374.1413N}, [TSO2008]')
        self.assertEqual(types['Rad'], '[LSK98], [RRC99]')
        self.assertEqual(types['Y*?'], '{2007MNRAS.374.1413N}')
        self.assertEqual(types['cor'], '[NW2007]')
        self.assertEqual(types['FIR'], '{2012ApJ...753L..35B}')


if __name__ == "__main__":
    unittest.main()
