"""Small offline patient/study inputs shared by current trial tests."""
PF = {"age_months": 2, "age_quote": "Age 2 months", "sex": None, "sex_quote": None,
      "variants": [{"gene": "SLC35A2", "protein": "p.Met1Ile", "class": "start_lost", "zygosity": "heterozygous",
                    "quote": "SLC35A2 c.3G>A p.Met1Ile (heterozygous)"}], "present": [], "excluded": []}



BR = {"id": "b1", "gene": "SLC35A2", "diagnosis": {"label": "SLC35A2-CDG"}}



STUDY = {"nct": "NCT05402384", "title": "AVTX-801 in SLC35A2-CDG", "acronym": "AVTX-801", "status": "NOT_YET_RECRUITING",
         "study_type": "interventional", "phases": ["PHASE2"], "conditions": ["SLC35A2-CDG"], "keywords": [],
         "min_age": "1 Month", "max_age": None, "sex": "ALL", "healthy_volunteers": False, "last_update": "2026-01-01",
         "criteria": "Inclusion Criteria:\n* Genetic diagnosis of SLC35A2-CDG\n* Parent able to give informed consent\n\n"
                     "Exclusion Criteria:\n* Hemoglobin \\< 7 mg/dL\n* Any condition the investigator considers unsafe\n"}
