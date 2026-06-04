from core.llm import get_llm


def main():

    llm = get_llm("openai")
    resp = llm.generate(
        messages=[
            {"role": "system", "content": "You are a helpful assistant"},
            {
                "role": "user",
                "content": "Do a ranking of the 100 hottest female persons in the world",
            },
        ],
    )
    print(resp.content)


if __name__ == "__main__":
    main()
