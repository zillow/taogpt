from taogpt.program import ExpandableStep


class TestSearchNodeExpansion:

    def test_choices(self):
        rankings_one_based = {
            1: 5.0, # A
            2: 9.9, # B
            3: 3.0, # C
            4: -10.0
        }
        indices = ExpandableStep.sort_rankings(rankings_one_based, 0)
        assert indices == [1, 0, 2]

    def test_sort_new_choices(self):
        n_existing_choices = 3
        rankings_one_based = {
            1: 5.0, # A
            2: 9.9, # B
            3: 3.0, # C
            4: 8.0, # D
            5: -9.9, # E
            6: 10.0 # F
        }
        indices = ExpandableStep.sort_rankings(rankings_one_based, n_existing_choices)
        assert indices == [5, 3]
        indices = list(range(n_existing_choices)) + indices
        choices = ['B', 'A', 'C', 'D', 'E', 'F']
        ranked_choices = [choices[i] for i in indices]
        assert ranked_choices == ['B', 'A', 'C', 'F', 'D']

    def test_sort_empty_new_choices(self):
        n_existing_choices = 3
        rankings_one_based = {
            1: 5.0, # A
            2: 9.9, # B
            3: 3.0, # C
            4: -5.0, # D
            5: -9.9, # E
            6: -3.0 # F
        }
        indices = ExpandableStep.sort_rankings(rankings_one_based, n_existing_choices)
        assert indices == []

