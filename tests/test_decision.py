from decision import utility_rank, lexicographic_optimize, pareto_front, social_welfare


def test_utility_rank_counts_preferences():
    result = utility_rank([[3, 2], [2, 1], [1, 0]])
    assert isinstance(result, dict)
    assert len(result) == 3


def test_lexicographic_optimize_chooses_best_vector():
    vectors = [(1, 0), (2, 0), (1, 2)]
    assert lexicographic_optimize(vectors) == [2]


def test_pareto_front_returns_non_dominated_vectors():
    vectors = [(3, 3), (5, 1), (1, 5)]
    front = pareto_front(vectors)
    assert tuple((3, 3)) in front


def test_social_welfare_aggregates():
    vectors = [(1, 2), (3, 4)]
    assert social_welfare(vectors) == 10
