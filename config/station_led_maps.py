# These mappings convert a station name to their respective LED position
# Currently it is assumed that the LED strip is connected
# at the southmost or westmost point of the train line
# If using a different configuration, the LED map will need to be updated

"""
Provides LED mapping configurations for MBTA train lines.
Each function returns a tuple of two dictionaries mapping station names to LED positions:
- First dictionary: Outbound direction
- Second dictionary: Inbound direction
"""

def red_led_map():
    return (
        # Mapping for one direction of travel - Northbound LEDs 
        {"Ashmont": 0, "Shawmut": 1, "Fields Corner": 2, "Savin Hill": 3, "JFK/UMass": 4, "Andrew": 5, "Broadway": 6, "South Station": 7, "Downtown Crossing": 8, "Park Street": 9, "Charles/MGH": 10, "Kendall/MIT": 11, "Central": 12, "Harvard": 13, "Porter": 14, "Davis": 15, "Alewife": 16, "Braintree": 38, "Quincy Adams": 37, "Quincy Center": 36, "Wollaston": 35, "North Quincy": 34},
        # Mapping for the opposite direction of travel - Southbound LEDs
        {"Ashmont": 33, "Shawmut": 32, "Fields Corner": 31, "Savin Hill": 30, "JFK/UMass": 29, "Andrew": 28, "Broadway": 27, "South Station": 26, "Downtown Crossing": 25, "Park Street": 24, "Charles/MGH": 23, "Kendall/MIT": 22, "Central": 21, "Harvard": 20, "Porter": 19, "Davis": 18, "Alewife": 17, "Braintree": 39, "Quincy Adams": 40, "Quincy Center": 41, "Wollaston": 42, "North Quincy": 43}
    )

def blue_led_map():
    return (
        # Mapping for one direction of travel (Southbound towards Bowdoin)
        {"Wonderland": 0, "Revere Beach": 1, "Beachmont": 2, "Suffolk Downs": 3, "Orient Heights": 4, "Wood Island": 5, "Airport": 6, "Maverick": 7, "Aquarium": 8, "State": 9, "Government Center": 10, "Bowdoin": 11},
        # Mapping for the opposite direction of travel (Northbound towards Wonderland)
        {"Wonderland": 23, "Revere Beach": 22, "Beachmont": 21, "Suffolk Downs": 20, "Orient Heights": 19, "Wood Island": 18, "Airport": 17, "Maverick": 16, "Aquarium": 15, "State": 14, "Government Center": 13, "Bowdoin": 12}
    )

def orange_led_map():
    return (
        # Mapping for one direction of travel (Southbound towards Forest Hills)
        {"Oak Grove": 0, "Malden Center": 1, "Wellington": 2, "Assembly": 3, "Sullivan Square": 4, "Community College": 5, "North Station": 6, "Haymarket": 7, "State": 8, "Downtown Crossing": 9, "Chinatown": 10, "Tufts Medical Center": 11, "Back Bay": 12, "Massachusetts Ave": 13, "Ruggles": 14, "Roxbury Crossing": 15, "Jackson Square": 16, "Stony Brook": 17, "Green Street": 18, "Forest Hills": 19},
        # Mapping for the opposite direction of travel (Northbound towards Oak Grove)
        {"Oak Grove": 39, "Malden Center": 38, "Wellington": 37, "Assembly": 36, "Sullivan Square": 35, "Community College": 34, "North Station": 33, "Haymarket": 32, "State": 31, "Downtown Crossing": 30, "Chinatown": 29, "Tufts Medical Center": 28, "Back Bay": 27, "Massachusetts Ave": 26, "Ruggles": 25, "Roxbury Crossing": 24, "Jackson Square": 23, "Stony Brook": 22, "Green Street": 21, "Forest Hills": 20}
    )

def green_b_led_map():
    return (
        # Mapping for one direction of travel (Eastbound towards Park Street)
        {"Boston College": 0, "South Street": 1, "Chestnut Hill Avenue": 2, "Chiswick Road": 3, "Sutherland Road": 4, "Washington Street": 5, "Warren Street": 6, "Allston Street": 7, "Griggs Street": 8, "Harvard Avenue": 9, "Packard's Corner": 10, "Babcock Street": 11, "Pleasant Street": 12, "St. Paul Street": 13, "Boston University West": 14, "Boston University Central": 15, "Boston University East": 16, "Blandford Street": 17, "Kenmore": 18},
        # Mapping for the opposite direction of travel (Westbound towards Boston College)
        {"Boston College": 37, "South Street": 36, "Chestnut Hill Avenue": 35, "Chiswick Road": 34, "Sutherland Road": 33, "Washington Street": 32, "Warren Street": 31, "Allston Street": 30, "Griggs Street": 29, "Harvard Avenue": 28, "Packard's Corner": 27, "Babcock Street": 26, "Pleasant Street": 25, "St. Paul Street": 24, "Boston University West": 23, "Boston University Central": 22, "Boston University East": 21, "Blandford Street": 20, "Kenmore": 19}
    )

def green_c_led_map():
    return (
        # Mapping for one direction of travel (Eastbound towards North Station)
        {"Cleveland Circle": 0, "Englewood Avenue": 1, "Dean Road": 2, "Tappan Street": 3, "Washington Square": 4, "Fairbanks Street": 5, "Brandon Hall": 6, "Summit Avenue": 7, "Coolidge Corner": 8, "Saint Paul Street": 9, "Kent Street": 10, "Hawes Street": 11, "Saint Mary's Street": 12, "Kenmore": 13},
        # Mapping for the opposite direction of travel (Westbound towards Cleveland Circle)
        {"Cleveland Circle": 27, "Englewood Avenue": 26, "Dean Road": 25, "Tappan Street": 24, "Washington Square": 23, "Fairbanks Street": 22, "Brandon Hall": 21, "Summit Avenue": 20, "Coolidge Corner": 19, "Saint Paul Street": 18, "Kent Street": 17, "Hawes Street": 16, "Saint Mary's Street": 15, "Kenmore": 14}
    )

def green_d_led_map():
    return (
        # Mapping for one direction of travel (Eastbound towards Government Center)
        {"Riverside": 0, "Woodland": 1, "Waban": 2, "Eliot": 3, "Newton Highlands": 4, "Newton Centre": 5, "Chestnut Hill": 6, "Reservoir": 7, "Beaconsfield": 8, "Brookline Hills": 9, "Brookline Village": 10, "Longwood": 11, "Fenway": 12, "Kenmore": 13},
        # Mapping for the opposite direction of travel (Westbound towards Riverside)
        {"Riverside": 27, "Woodland": 26, "Waban": 25, "Eliot": 24, "Newton Highlands": 23, "Newton Centre": 22, "Chestnut Hill": 21, "Reservoir": 20, "Beaconsfield": 19, "Brookline Hills": 18, "Brookline Village": 17, "Longwood": 16, "Fenway": 15, "Kenmore": 14}
    )

def green_e_led_map():
    return (
        # Mapping for one direction of travel (Eastbound towards Lechmere)
        {"Heath Street": 0, "Back of the Hill": 1, "Riverway": 2, "Mission Park": 3, "Fenwood Road": 4, "Brigham Circle": 5, "Longwood Medical Area": 6, "Museum of Fine Arts": 7, "Northeastern University": 8, "Symphony": 9, "Prudential": 10, "Copley": 11, "Arlington": 12, "Boylston": 13, "Park Street": 14, "Government Center": 15, "Lechmere": 16},
        # Mapping for the opposite direction of travel (Westbound towards Heath Street)
        {"Heath Street": 33, "Back of the Hill": 32, "Riverway": 31, "Mission Park": 30, "Fenwood Road": 29, "Brigham Circle": 28, "Longwood Medical Area": 27, "Museum of Fine Arts": 26, "Northeastern University": 25, "Symphony": 24, "Prudential": 23, "Copley": 22, "Arlington": 21, "Boylston": 20, "Park Street": 19, "Government Center": 18, "Lechmere": 17}
    )

# Dictionary mapping line names to their respective LED map functions
station_led_maps = {
    "Red": red_led_map,
    "Blue": blue_led_map,
    "Orange": orange_led_map,
    "Green-B": green_b_led_map,
    "Green-C": green_c_led_map,
    "Green-D": green_d_led_map,
    "Green-E": green_e_led_map
}
