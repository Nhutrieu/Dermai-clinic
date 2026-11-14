from pathlib import Path
import importlib.util
import numpy as np
import pytest

path=Path(__file__).resolve().parents[1]/'training/evaluate_application_model.py'
spec=importlib.util.spec_from_file_location('application_evaluation',path)
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)


def test_rejected_cases_stay_in_full_denominators():
    rows=[dict(label='Lupus',disease='Lupus',http_status=200,uncertain=False),
          dict(label='Lupus',disease=None,http_status=422,uncertain=None,detail='quality'),
          dict(label='Psoriasis',disease='Lupus',http_status=200,uncertain=True)]
    s=m.metrics(rows)
    assert s['coverage']==pytest.approx(2/3)
    assert s['accuracy_on_returned']==.5
    assert s['correct_return_rate']==pytest.approx(1/3)
    assert s['per_class']['Lupus']['recall']==.5
    assert s['per_class']['Lupus']['precision']==.5
    assert s['per_class']['SkinCancer']['recall'] is None
    assert s['confusion_matrix_8x9'][3][8]==1
    assert s['uncertain_returned']==1


def test_all_rejected_does_not_invent_selective_accuracy():
    s=m.metrics([dict(label='SkinCancer',disease=None,http_status=422,detail='OOD')])
    assert s['accuracy_on_returned'] is None and s['correct_return_rate']==0
    assert s['per_class']['SkinCancer']['recall']==0


def test_leakage_checks_both_bytes_pixels_cases_and_review():
    row=dict(path='SkinDisease/scin-v1/external_test/Lupus/case1/photo.jpg',sha256='byte',pixel_sha256='pixel',dhash64='000000000000000f')
    reasons,near=m.leakage_reasons(row,{'byte'},{'pixel'},{'case1'},{'byte'},m.HammingTree([0]))
    assert set(reasons)=={'same_bytes_as_protected','same_RGB_pixels_as_protected','same_SCIN_case_as_protected','historically_reviewed_same_scene'}
    assert not near  # Hamming distance4 does not qualify.
    row['dhash64']='0000000000000007'
    assert m.leakage_reasons(row,set(),set(),set(),set(),m.HammingTree([0]))[0]==['conservative_dhash_distance_le3']


def test_hamming_tree_matches_bruteforce():
    rng=np.random.default_rng(42);values=[int(v) for v in rng.integers(0,2**63,200,dtype=np.int64)];values += [0,1,3,7,15]
    tree=m.HammingTree(values)
    for q in values[::10]+[0,5]:
        assert set(tree.query(q))=={i for i,v in enumerate(values) if (q^v).bit_count()<=3}
