from __future__ import annotations

import json
from pathlib import Path


TEMPLATES = [
    (
        "medium",
        "What river flows through the city where Ada Lovelace was born?",
        "River Thames",
        ("Ada Lovelace", "Ada Lovelace was born in London, England."),
        ("London", "London is crossed by the River Thames."),
        "London",
        "incomplete_multi_hop",
    ),
    (
        "medium",
        "Which ocean borders the country whose capital is Lima?",
        "Pacific Ocean",
        ("Lima", "Lima is the capital city of Peru."),
        ("Peru", "Peru borders the Pacific Ocean."),
        "Atlantic Ocean",
        "wrong_final_answer",
    ),
    (
        "hard",
        "What sea borders the country where Petra is located?",
        "Dead Sea",
        ("Petra", "Petra is a historical city in Jordan."),
        ("Jordan", "Jordan borders the Dead Sea to the west."),
        "Red Sea",
        "entity_drift",
    ),
    (
        "hard",
        "Which mountain range contains the highest mountain in Nepal?",
        "Himalayas",
        ("Nepal", "Mount Everest is the highest mountain in Nepal."),
        ("Mount Everest", "Mount Everest is part of the Himalayas."),
        "Andes",
        "entity_drift",
    ),
    (
        "medium",
        "What language family includes the official language of Brazil?",
        "Romance",
        ("Brazil", "The official language of Brazil is Portuguese."),
        ("Portuguese", "Portuguese is a Romance language."),
        "Portuguese",
        "incomplete_multi_hop",
    ),
    (
        "easy",
        "Which university employed the author of The Hobbit as a professor?",
        "Oxford University",
        ("The Hobbit", "The Hobbit was written by J. R. R. Tolkien."),
        ("J. R. R. Tolkien", "Tolkien was a professor at Oxford University."),
        "Cambridge University",
        "wrong_final_answer",
    ),
    (
        "medium",
        "What instrument was played by the composer of The Four Seasons?",
        "violin",
        ("The Four Seasons", "The Four Seasons was composed by Antonio Vivaldi."),
        ("Antonio Vivaldi", "Antonio Vivaldi was a virtuoso violinist."),
        "piano",
        "wrong_final_answer",
    ),
    (
        "medium",
        "Which continent contains the country whose capital is Nairobi?",
        "Africa",
        ("Nairobi", "Nairobi is the capital of Kenya."),
        ("Kenya", "Kenya is a country in Africa."),
        "Kenya",
        "incomplete_multi_hop",
    ),
    (
        "hard",
        "What currency is used in the country containing Kyoto?",
        "Japanese yen",
        ("Kyoto", "Kyoto is a city in Japan."),
        ("Japan", "The currency of Japan is the Japanese yen."),
        "Chinese yuan",
        "entity_drift",
    ),
    (
        "medium",
        "Which sea borders the country whose capital is Athens?",
        "Aegean Sea",
        ("Athens", "Athens is the capital of Greece."),
        ("Greece", "Greece borders the Aegean Sea."),
        "Mediterranean Sea",
        "wrong_final_answer",
    ),
    (
        "easy",
        "What scientific field was studied by the person who formulated the laws of motion?",
        "mathematics",
        ("Laws of motion", "The laws of motion were formulated by Isaac Newton."),
        ("Isaac Newton", "Isaac Newton was a physicist and mathematician."),
        "Isaac Newton",
        "incomplete_multi_hop",
    ),
    (
        "hard",
        "Which desert lies in the country whose capital is Ulaanbaatar?",
        "Gobi Desert",
        ("Ulaanbaatar", "Ulaanbaatar is the capital of Mongolia."),
        ("Mongolia", "A large part of the Gobi Desert lies in Mongolia."),
        "Sahara",
        "entity_drift",
    ),
    (
        "medium",
        "What is the capital of the country containing Barcelona?",
        "Madrid",
        ("Barcelona", "Barcelona is a city in Spain."),
        ("Spain", "Madrid is the capital of Spain."),
        "Barcelona",
        "incomplete_multi_hop",
    ),
    (
        "hard",
        "Which river crosses the capital of Hungary?",
        "Danube",
        ("Hungary", "Budapest is the capital of Hungary."),
        ("Budapest", "The Danube flows through Budapest."),
        "Rhine",
        "entity_drift",
    ),
    (
        "medium",
        "What language is official in the country containing Quebec City?",
        "French",
        ("Quebec City", "Quebec City is in Canada."),
        ("Canada", "French is one of Canada's official languages."),
        "Spanish",
        "wrong_final_answer",
    ),
    (
        "easy",
        "Which planet was studied by the scientist who discovered its four largest moons?",
        "Jupiter",
        ("Galilean moons", "The four largest moons were discovered by Galileo Galilei."),
        ("Galileo Galilei", "Galileo observed and studied Jupiter."),
        "Galileo Galilei",
        "incomplete_multi_hop",
    ),
    (
        "hard",
        "Which ocean surrounds the island country whose capital is Malé?",
        "Indian Ocean",
        ("Malé", "Malé is the capital of the Maldives."),
        ("Maldives", "The Maldives is an island country in the Indian Ocean."),
        "Pacific Ocean",
        "wrong_final_answer",
    ),
    (
        "medium",
        "What is the currency of the country whose capital is Bern?",
        "Swiss franc",
        ("Bern", "Bern is the de facto capital of Switzerland."),
        ("Switzerland", "The currency of Switzerland is the Swiss franc."),
        "euro",
        "entity_drift",
    ),
    (
        "hard",
        "Which mountain range includes Mont Blanc?",
        "Alps",
        ("Mont Blanc", "Mont Blanc lies on the border of France and Italy."),
        ("European ranges", "Mont Blanc is the highest mountain in the Alps."),
        "Pyrenees",
        "wrong_final_answer",
    ),
    (
        "medium",
        "What is the capital of the country where Machu Picchu is located?",
        "Lima",
        ("Machu Picchu", "Machu Picchu is located in Peru."),
        ("Peru", "Lima is the capital of Peru."),
        "Peru",
        "incomplete_multi_hop",
    ),
]


def build_dataset() -> list[dict]:
    rows: list[dict] = []
    for repetition in range(1, 6):
        for index, item in enumerate(TEMPLATES, start=1):
            difficulty, question, answer, first, second, wrong, failure_mode = item
            rows.append(
                {
                    "qid": f"custom_{index:02d}_{repetition}",
                    "difficulty": difficulty,
                    "question": question,
                    "gold_answer": answer,
                    "context": [
                        {"title": first[0], "text": first[1]},
                        {"title": second[0], "text": second[1]},
                    ],
                    "mock_wrong_answer": wrong,
                    "mock_failure_mode": failure_mode,
                }
            )
    return rows


def main() -> None:
    output = Path("data/hotpot_custom_100.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(build_dataset(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Saved {len(build_dataset())} questions to {output}")


if __name__ == "__main__":
    main()
