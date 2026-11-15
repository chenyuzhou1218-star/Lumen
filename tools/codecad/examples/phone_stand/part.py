"""A phone stand. Change PHONE to the thickness of your phone with its case."""
import cad

PHONE = 11.0     # the phone with its case
GAP = .6         # room to slide in
TILT = 15        # degrees back
WIDTH = 70

base = cad.rounded_plate(80, 62, 5, 6).at(0, 0, 2.5)
back = cad.box(WIDTH, 7, 58).turn(x=-TILT).at(0, 16, 31)
BACK_FACE = 5.4  # where the back's front surface meets the base
lip = cad.box(WIDTH, 5, 12).at(0, BACK_FACE - PHONE - GAP - 2.5, 8)
stand = (base + back + lip).on_bed()
cad.part('phone_stand', stand, material='PLA', x=80, y=62)
