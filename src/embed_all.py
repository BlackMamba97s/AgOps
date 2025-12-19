from embedding.sme.kubepython_sme import KubePythonSme
from embedding.sme.kubernetes_sme import KubernetesSme
from bs4 import BeautifulSoup
from git import Repo
import tempfile
from dotenv import load_dotenv
import nltk
nltk.download('punkt_tab')
nltk.download('averaged_perceptron_tagger_eng')
load_dotenv(override=True)

def get_main_only(content: BeautifulSoup) -> str:
    list_of_td = content.select(".td-content")
    return list_of_td[0].get_text() if len(content.select(".td-content")) == 1 else ""


def main():
#     with tempfile.TemporaryDirectory() as tmp:
#         Repo.clone_from("https://github.com/kubernetes-client/python.git", tmp)
#         sme1 = KubePythonSme()
#         sme1.loadMarkdown(f"{tmp}\kubernetes\\docs\\")

    sme2 = KubernetesSme()
    sme2.loadSiteMap(
        url="https://kubernetes.io/en/sitemap.xml",
        filter_urls=["https:\/\/kubernetes\.io\/docs\/.*"],
        parsing_function=get_main_only)


if __name__ == "__main__":
    main()
