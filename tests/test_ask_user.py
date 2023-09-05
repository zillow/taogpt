from taogpt.orchestrator import ask_questions
from taogpt.parsing import parse_ordered_list


class TestAskUser:

    def test_multiple_questions(self):
        questions = [
            "Have you eaten your dinner?",
            "What did you eat?"
        ]
        question_text = f"""
I need to ask some questions.

1. {questions[0]}
2. {questions[1]}
        """
        question_list = parse_ordered_list(question_text)
        assert question_list == questions

        answers = ["Yes", "Lobsters,\nlots of them."]

        def _ask(prompt):
            if questions[0] in prompt:
                return answers[0]
            elif questions[1] in prompt:
                return answers[1]
            return "Don't know"

        answer_text = ask_questions(_ask, question_list)
        assert answer_text == f"""1. Yes
2. Lobsters,
   lots of them.\n"""
        answer_list = parse_ordered_list(answer_text)
        assert [a.replace('\n', ' ') for a in answers] == answer_list
