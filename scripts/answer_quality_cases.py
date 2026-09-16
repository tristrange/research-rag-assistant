"""Reference-labelled cases not used in the original 12-question retrieval tuning.

These are assistant-authored labels on the same paper, with overlapping topics;
they are an exploratory evaluation set, not an independent benchmark.
"""

from app.answer_evaluation import AnswerEvaluationCase


PAPER_SHA256 = "072e84623519c3de66e77c6137e4ff92dd315409a639406e5d767bc4d5b262ca"

ANSWER_CASES: list[AnswerEvaluationCase] = [
    {
        "id": "c26-body-mass-loss",
        "question": "How much body mass had the cachectic C26 mice lost at termination, and when was this measured?",
        "answerable": True,
        "reference_answer": "They had a 20% reduction in body mass 20 days after inoculation.",
        "evidence": [{"document": "sample.pdf", "page": 3,
                      "quote": "cachectic mice had a 20% reduction in body mass 20 days after inoculation"}],
    },
    {
        "id": "c26-muscle-glucose-uptake",
        "question": "By approximately how much was insulin-stimulated glucose uptake elevated in soleus and EDL muscle from cachectic C26 mice?",
        "answerable": True,
        "reference_answer": "The response was about 80% higher in soleus and 35–40% higher in EDL than in weight-stable and control mice.",
        "evidence": [
            {"document": "sample.pdf", "page": 3,
             "quote": "cachectic mice showed ∼80% higher response to insulin"},
            {"document": "sample.pdf", "page": 3,
             "quote": "cachectic mice showed a 35—40% elevation in insulin response"},
        ],
    },
    {
        "id": "food-restriction-protocol",
        "question": "How long were healthy mice food-restricted, and by approximately how much was their intake reduced?",
        "answerable": True,
        "reference_answer": "Food intake was reduced by approximately 30% for the final three days.",
        "evidence": [{"document": "sample.pdf", "page": 2,
                      "quote": "The last three days, the food intake was reduced by approximately 30%"}],
    },
    {
        "id": "food-restriction-body-mass",
        "question": "What average body-mass change followed three days of food restriction?",
        "answerable": True,
        "reference_answer": "Food-restricted mice lost 1.2 g, or 3.9%, while controls gained 0.7 g, or 2.1%.",
        "evidence": [{"document": "sample.pdf", "page": 6,
                      "quote": "food-restricted mice lost 1.2 g (− 3.9%) body weight on average after 3 days"}],
    },
    {
        "id": "food-restriction-glucose-tolerance",
        "question": "How did three days of food restriction change glucose-tolerance incremental AUC?",
        "answerable": True,
        "reference_answer": "It improved glucose tolerance, reducing incremental AUC by 56% compared with ad-libitum-fed controls.",
        "evidence": [{"document": "sample.pdf", "page": 7,
                      "quote": "food-restriction markedly improved glucose tolerance with a 56% reduction in incremental AUC"}],
    },
    {
        "id": "food-restriction-grip-strength",
        "question": "Did the short food-restriction intervention reduce grip strength?",
        "answerable": True,
        "reference_answer": "No. Grip strength was unaffected after the three-day intervention.",
        "evidence": [{"document": "sample.pdf", "page": 7,
                      "quote": "grip strength was unaffected"}],
    },
    {
        "id": "cachectic-akt-phosphorylation",
        "question": "What insulin-stimulated fold changes in AKT phosphorylation were observed at Thr308 and Ser473 in cachectic soleus muscle?",
        "answerable": True,
        "reference_answer": "pAKT Thr308 increased 4.4-fold and pAKT Ser473 increased 8.5-fold.",
        "evidence": [
            {"document": "sample.pdf", "page": 7, "quote": "even higher 4.4-fold increase by insulin"},
            {"document": "sample.pdf", "page": 7, "quote": "cachectic mice exhibited a remarkable 8.5-fold increase"},
        ],
    },
    {
        "id": "kpc-mouse-strain",
        "question": "Which mouse strain and age were used for the KPC studies?",
        "answerable": True,
        "reference_answer": "The KPC studies used 14-week-old male C57BL/6JBomTac mice.",
        "evidence": [{"document": "sample.pdf", "page": 2,
                      "quote": "14-week-old male C57BL/6JBomTac"}],
    },
    {
        "id": "glucose-tolerance-protocol",
        "question": "For cohorts 1, 3, and 4, how long were mice fasted before the glucose tolerance test and when was blood glucose measured?",
        "answerable": True,
        "reference_answer": "They were fasted for four hours, with blood glucose measured at 0, 20, 40, 60, 90, and 120 minutes.",
        "evidence": [
            {"document": "sample.pdf", "page": 2,
             "quote": "All mice were fasted for 4 h before the glucose tolerance test"},
            {"document": "sample.pdf", "page": 2,
             "quote": "Blood glucose levels were determined at timepoints 0, 20, 40, 60, 90, and 120 min"},
        ],
    },
    {
        "id": "immunoblot-loading-control",
        "question": "What loading control was used for the muscle immunoblots, and why?",
        "answerable": True,
        "reference_answer": "Coomassie staining was used because the authors considered it a better loading control than commonly used housekeeping proteins.",
        "evidence": [{"document": "sample.pdf", "page": 3,
                      "quote": "Coomassie stains were used as control for loading"}],
    },
    {
        "id": "grip-strength-readout",
        "question": "How many grip-strength measurements were made per mouse, and which measurement was used?",
        "answerable": True,
        "reference_answer": "The measurement was repeated three times per mouse, and the maximum was used as the final force readout.",
        "evidence": [{"document": "sample.pdf", "page": 2,
                      "quote": "This was repeated three times for each mouse, and the maximal recording was used"}],
    },
    {
        "id": "statistics-software",
        "question": "Which software and version were used for the statistical analysis?",
        "answerable": True,
        "reference_answer": "GraphPad Prism 10 was used for the statistical analysis.",
        "evidence": [{"document": "sample.pdf", "page": 3,
                      "quote": "analyzed using GraphPad Prism 10"}],
    },
    {
        "id": "significance-threshold",
        "question": "What significance level did the authors use for the statistical tests?",
        "answerable": True,
        "reference_answer": "The significance level was alpha = 0.05.",
        "evidence": [{"document": "sample.pdf", "page": 3,
                      "quote": "The significance level was set at α = 0.05"}],
    },
    {
        "id": "tumor-mass-correction",
        "question": "How did the authors correct body-composition measurements for the tumor?",
        "answerable": True,
        "reference_answer": "For cohorts 1, 3, and 4, dissected tumor mass was subtracted from total body weight and lean mass.",
        "evidence": [{"document": "sample.pdf", "page": 2,
                      "quote": "The tumor mass from dissections was subtracted from the total body weight and lean mass"}],
    },
    {
        "id": "isolated-muscle-insulin",
        "question": "What insulin concentration and stimulation duration were used for isolated muscles?",
        "answerable": True,
        "reference_answer": "Isolated muscles underwent 20 minutes of maximal insulin stimulation at 60 nM, after a five-minute pre-incubation.",
        "evidence": [{"document": "sample.pdf", "page": 3,
                      "quote": "20 min of either control (vehicle) or maximal insulin stimulation (60 nM)"}],
    },
    {
        "id": "kpc-food-intake",
        "question": "Was food intake lower in KPC tumor-bearing mice than in controls?",
        "answerable": True,
        "reference_answer": "No change in food intake was observed in the KPC mice.",
        "evidence": [{"document": "sample.pdf", "page": 6,
                      "quote": "these changes were observed without any changes in food intake of the KPC mice"}],
    },
    {
        "id": "female-mice",
        "question": "How did cachexia affect insulin-stimulated glucose uptake in female mice?",
        "answerable": False,
        "reference_answer": "The paper does not report experiments in female mice.",
        "evidence": [],
    },
    {
        "id": "human-survival",
        "question": "What effect did improved glucose tolerance have on survival in human cancer patients?",
        "answerable": False,
        "reference_answer": "The paper reports mouse experiments and does not measure human survival outcomes.",
        "evidence": [],
    },
    {
        "id": "long-term-food-restriction",
        "question": "What happened to muscle insulin responsiveness after six months of food restriction?",
        "answerable": False,
        "reference_answer": "The paper only reports a three-day food-restriction intervention, not a six-month intervention.",
        "evidence": [],
    },
    {
        "id": "drug-treatment",
        "question": "Which drug most effectively reversed cachexia in the authors' experiments?",
        "answerable": False,
        "reference_answer": "The reported experiments did not compare drug treatments for reversing cachexia.",
        "evidence": [],
    },
]
