import glob
import os
import pickle
import re
import requests
import sys
from scholar import txt 
from scholar import ScholarConf
from scholar import ScholarQuerier
from scholar import SearchScholarQuery
from scholar import UrlScholarQuery
from tika import parser

def sanitize(s):
    s = s.encode('ascii','ignore').lower().replace('\n', ' ')
    s = re.sub(r'\s+', ' ', s)
    s = re.sub(r'-\s*', '', s)
    return s

if __name__ == '__main__':
    search_term = sys.argv[1]
    output_dir = sys.argv[2]
    if not os.path.exists(output_dir):
        os.mkdir(output_dir)
    ScholarConf.COOKIE_JAR_FILE = output_dir + '/cookies.txt'
    if not os.path.exists(output_dir + '/search.pkl'):
        # (1) Find the paper that's the top search term.
        search_query = SearchScholarQuery()
        search_query.set_phrase(search_term)
        search_querier = ScholarQuerier()
        search_querier.send_query(search_query)
        # (2) Go look at its citations.
        for x in search_querier.articles:
            print(x.attrs['title'][0])
        url = search_querier.articles[0].attrs['url_citations'][0]
        lead_title = search_querier.articles[0].attrs['title'][0]
        query = UrlScholarQuery(url=url)
        querier = ScholarQuerier()
        querier.send_query(query)
        querier.save_cookies()
        # Download articles.
        if False:
            for article in querier.articles:
                pdf_url = article.attrs['url_pdf'][0]
                file_name = pdf_url.split('/')[-1]
                if file_name[-4:] != '.pdf':
                    file_name += '.pdf'
                response = requests.get(pdf_url)
                with open(output_dir + '/' + file_name, 'wb') as f:
                    f.write(response.content)
        # Save query results in pickle file.
        with open(output_dir + '/search.pkl', 'wb') as f:
            savedict = dict(url=url, lead_title=lead_title,
                            query=query, search_query=search_query,
                            querier=querier, search_querier=search_querier)
    else:
        with open(output_dir + '/search.pkl', 'rb') as f:
            pkl = pickle.load(f)
            url, lead_title = pkl['url'], pkl['lead_title']
            search_querier, querier = pkl['search_querier'], pkl['querier']
    # Process.
    for file_name in sorted(glob.glob(output_dir + '/*.pdf')):
        print(file_name)
        pdf = parser.from_file(output_dir + '/' + file_name)
        ref_idx = pdf['content'].lower().find('references')
        # Extract the element corresponding to the lead title.
        full_text, ref_text = pdf['content'][:ref_idx], pdf['content'][ref_idx:]
        sanitized_title = lead_title.lower().replace('-', '')
        if re.search(r'^\[\d+\]', ref_text, flags=re.MULTILINE) or \
           re.search(r'^\d\.', ref_text, flags=re.MULTILINE):
            if re.search(r'^\[\d+\]', ref_text, flags=re.MULTILINE):
                regex = r'^\[\d+\]'
            else:
                regex = r'^\d+\.'
            cite_lines = re.split(regex, ref_text, flags=re.MULTILINE)[1:]
            cite_vals = re.findall(regex, ref_text, flags=re.MULTILINE)
            assert len(cite_lines) == len(cite_vals)
            found = False
            for line, val in zip(cite_lines, cite_vals):
                if sanitize(line).find(sanitized_title) >= 0:
                    found = True
                    print(val, regex, sanitize(line))
                    # Go find the citation in context.
                    num = re.findall(r'\d+', val)[0]
                    all_lines = re.split(r'\[\d[,\d]*\]', sanitize(full_text))
                    all_vals = re.findall(r'\[\d[,\d]*\]', sanitize(full_text))
                    matching_idx = []
                    for j in range(len(all_vals)):
                        citations = set(map(int, all_vals[j][1:-1].split(',')))
                        if num in citations:
                            matching_idx.append(num) 
                    break
            if not found:
                print('no citation found')
