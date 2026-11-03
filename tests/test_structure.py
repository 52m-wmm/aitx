"""AlphaFold structure facts: SASA / RSA geometry, isoform mapping, neighbours, annotate() wiring."""
import json
import math

import pytest

from aitx.variant import structure as S


def atom_line(serial, name, resname, res, xyz, b=90.0, el=None):
    el = el or name[0]
    return (f"ATOM  {serial:>5} {name:<4} {resname} A{res:>4}    "
            f"{xyz[0]:>8.3f}{xyz[1]:>8.3f}{xyz[2]:>8.3f}  1.00{b:>6.2f}           {el:>2}")


def test_parse_pdb_reads_coordinates_and_plddt():
    atoms = S.parse_pdb(atom_line(1, "CA", "ASP", 34, (1.0, 2.0, 3.0), b=79.19))
    assert atoms == [{"res": 34, "resname": "ASP", "name": "CA", "el": "C", "xyz": (1.0, 2.0, 3.0), "b": 79.19}]


def test_isolated_atom_sasa_is_full_sphere():
    atoms = S.parse_pdb(atom_line(1, "CA", "GLY", 1, (0, 0, 0)))
    want = 4 * math.pi * (1.70 + 1.4) ** 2
    assert S.residue_sasa(atoms, 1) == pytest.approx(want, rel=1e-9)


def test_buried_atom_has_no_sasa_and_neighbour_halves_exposure():
    centre = atom_line(1, "CA", "GLY", 1, (0, 0, 0))
    # a dense shell of carbon atoms at 3 Å hides the centre completely
    shell = [atom_line(i + 2, "C", "ALA", 2, tuple(3.0 * c for c in p)) for i, p in enumerate(S.sphere_points(200))]
    assert S.residue_sasa(S.parse_pdb("\n".join([centre] + shell)), 1) == 0.0
    # one touching neighbour removes part, not all
    pair = S.parse_pdb("\n".join([centre, atom_line(2, "C", "ALA", 2, (3.4, 0, 0))]))
    full = 4 * math.pi * 3.1 ** 2
    assert 0.6 * full < S.residue_sasa(pair, 1) < full


def test_neighbours_within_8A():
    atoms = S.parse_pdb("\n".join([atom_line(1, "CA", "LEU", 10, (0, 0, 0)), atom_line(2, "CA", "ASP", 11, (7.9, 0, 0)),
                                   atom_line(3, "CA", "GLY", 12, (8.2, 0, 0))]))
    assert S.neighbours(atoms, 10) == [{"position": 11, "aa": "Asp", "min_distance_A": 7.9}]


def test_map_position_identical_and_isoform():
    assert S.map_position("MKLV", "MKLV", 3) == {"model_position": 3, "method": "identical sequence"}
    ref = "MAAAA" + "QQQQQ" + "KLMNPRSTVW"       # RefSeq isoform has an extra 5-aa exon
    model = "MAAAA" + "KLMNPRSTVW"
    m = S.map_position(ref, model, 13)            # 'P' after the extra exon
    assert m["model_position"] == 8 and model[7] == ref[12] and m["method"] == "identical sequence block"
    assert S.map_position(ref, model, 7)["model_position"] is None      # inside the extra exon


def test_plddt_bands():
    assert [S.plddt_band(x) for x in (95, 80, 60, 40)] == ["very_high", "confident", "low", "very_low"]


def test_annotate_records_source_rsa_and_flags(monkeypatch, tmp_path):
    seq = "MDLG"
    pdb = "\n".join([atom_line(1, "N", "MET", 1, (0, 0, 0), 95), atom_line(2, "CA", "ASP", 2, (20, 0, 0), 60),
                     atom_line(3, "CB", "ASP", 2, (21.5, 0, 0), 60), atom_line(4, "CA", "LEU", 3, (25, 0, 0), 60),
                     atom_line(5, "CA", "GLY", 4, (60, 0, 0), 90)])
    api = [{"entryId": "AF-P00001-F1", "uniprotAccession": "P00001", "latestVersion": 6,
            "modelCreatedDate": "2025-08-01T00:00:00Z", "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-P00001-F1-model_v6.pdb",
            "uniprotSequence": seq, "globalMetricValue": 70.0}]

    def fake_get(url, **kw):
        if "uniprot" in url:
            text = "Entry\tRefSeq\nP00001\tNP_1.1 [P00001-1];\n"
        elif "/api/prediction/" in url:
            text = json.dumps(api)
        else:
            text = pdb
        return S.http.Fetched(url, text, 1793700000, True)

    monkeypatch.setattr(S.http, "get", fake_get)
    monkeypatch.setattr(S, "STRUCT_DIR", tmp_path)
    r = S.annotate("NP_1.1", "TEST", seq, 2, lost_from=3)
    assert r["source"]["alphafold_entry"] == "AF-P00001-F1" and r["source"]["model_version"] == 6
    assert r["source"]["accessed_at"] == 1793700000 and (tmp_path / "AF-P00001-F1-model_v6.pdb").exists()
    assert r["residue"]["match"] and r["mapping"]["method"] == "identical sequence"
    assert r["plddt"] == {"value": 60.0, "band": "low", "reliable": False, "note": r["plddt"]["note"]}
    assert r["rsa"]["class"] == "exposed" and r["rsa"]["reliable"] is False
    assert r["lost_model_range"] == [3, 4]
    assert [n["position"] for n in r["neighbours_8A"]] == [3]
