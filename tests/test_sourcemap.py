from parsemon.sourcemap import (display_location, find_line_in_indices,
                                find_linebreak_indices)


def test_display_location_contains_the_actual_line_number():
    line = 283
    assert str(line) in display_location(line=line, column=0)

def test_dist_location_contains_the_actual_column_number_supplied():
    column = 465
    assert str(column) in display_location(line=0, column=column)

def test_find_linebreak_indices_returns_empty_list_for_online_string():
    msg = "12345"
    assert find_linebreak_indices(msg) == []

def test_find_linebreak_indices_returns_list_as_long_as_msg_when_only_linebreaks():
    msg = '\n\n\n\n'
    assert len(find_linebreak_indices(msg)) == len(msg)

def test_find_line_in_indices_returns_1_for_index_0():
    assert find_line_in_indices(0,[5,10]) == 1

def test_find_line_in_indices_returns_2_after_first_linebreak():
    indices = [4]
    assert find_line_in_indices(5,indices) == 2

def test_find_line_in_indices_returns_2_in_middle_of_two_linebreaks():
    indices = [0,2]
    assert find_line_in_indices(1,indices) == 2

def test_find_line_in_indices_returns_1_for_index_0_if_first_char_is_linebreak():
    indices = [0]
    assert find_line_in_indices(0,indices) == 1
