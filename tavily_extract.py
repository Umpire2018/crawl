from tavily import TavilyClient

# Step 1. Instantiating your TavilyClient
tavily_client = TavilyClient(api_key="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")

# Step 2. Defining the list of URLs to extract content from
urls = [
    "https://apnews.com/article/hawaii-wildfire-maui-dora-winds-ec23c16abfbeb6ba689f1a98263720db",
]

# Step 3. Executing the extract request
response = tavily_client.extract(urls=urls, include_images=True)

print(response)

# Step 4. Printing the extracted raw content
for result in response["results"]:
    print(f"URL: {result['url']}")
    print(f"Raw Content: {result['raw_content']}")
    print(f"Images: {result['images']}\n")

# Note that URLs that could not be extracted will be stored in response["failed_results"]
