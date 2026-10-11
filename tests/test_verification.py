from verification import check_field, check_abv, check_warning, WARNING

def test_brand_ignores_case_and_punctuation():
    assert check_field('Brand', "Stone's Throw", 'STONE’S THROW').status == 'Match'

def test_missing_brand_is_not_auto_rejected():
    assert check_field('Brand', 'Old Tom', 'Unknown').status == 'Needs Review'

def test_abv_match():
    assert check_abv('45', '45% Alc./Vol.').status == 'Match'

def test_abv_mismatch():
    assert check_abv('45', '40% Alc./Vol.').status == 'Mismatch'

def test_warning_requires_manual_format_review():
    assert check_warning(WARNING).status == 'Needs Review'

def test_warning_title_case_not_accepted():
    assert 'not confirmed' in check_warning(WARNING.replace('GOVERNMENT WARNING:', 'Government Warning:')).detail
