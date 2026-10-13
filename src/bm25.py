"""BM25 关键词检索：手写实现 + jieba 中文分词。"""
import math
import jieba
from collections import Counter, defaultdict

def tokenize(text: str) -> list[str]:
    """把句子切成词，过滤空白。"""
    return [w for w in jieba.lcut(text) if w.strip()]


class BM25:
    """手写 Okapi BM25。构造时传入所有文档的分词结果（list[list[str]]）。"""

    def __init__(self, docs, k1=1.5, b=0.75):
        self.k1 = k1
        self.b = b
        self.N = len(docs)
        # 算 df —— {词: 出现在几个文档里}
        self.df = defaultdict(int)
        # 算 doc_len —— 每个文档总词数
        self.doc_len = []
        # 算 doc_tf —— 每个文档里每个词的词频 {词: 次数}
        self.doc_tf = []

        for doc in docs:
            # 文档长度
            length = len(doc)
            self.doc_len.append(length)
            # 词频统计
            tf = Counter(doc)
            self.doc_tf.append(tf)
            # 更新 df（每个词只要出现在该文档中，df 加 1）
            for word in set(doc):
                self.df[word] += 1
        # 算 avgdl —— 所有文档平均长度
        self.avgdl = sum(self.doc_len) / self.N if self.N else 0.0

        self.df = dict(self.df)    # 将 defaultdict 转为普通 dict，方便查询

    def _idf(self, t):
        """IDF = ln((N - n(t) + 0.5) / (n(t) + 0.5) + 1)。"""
        n = self.df.get(t, 0)  # 出现该词的文档数
        return math.log((self.N - n + 0.5) / (n + 0.5) + 1)

    def score(self, query_tokens):
        """对每个文档套公式求和，返回 [分数...] 列表（和 docs 一一对应）。"""
        scores = []
        for idx, tf_dict in enumerate(self.doc_tf):
            doc_len = self.doc_len[idx]
            # 长度归一化因子分母
            denominator = 1 - self.b + self.b * (doc_len / self.avgdl)
            total = 0.0
            for token in query_tokens:
                f = tf_dict.get(token, 0)
                if f == 0:
                    continue
                idf = self._idf(token)
                # BM25 词项分数
                term_score = idf * (f * (self.k1 + 1)) / (f + self.k1 * denominator)
                total += term_score
            scores.append(total)
        return scores


# 测试
if __name__ == "__main__":
    docs = [["人工", "智能", "岗位"], ["前端", "面试", "岗位"]]
    bm25 = BM25(docs)

    print("df:", bm25.df)           
    # {'人工': 1, '智能': 1, '岗位': 2, '前端': 1, '面试': 1}

    print("doc_len:", bm25.doc_len)  
    # [3, 3]

    print("avgdl:", bm25.avgdl)      
    # 3.0

    print("doc_tf:", bm25.doc_tf)    
    # [Counter({'人工':1, '智能':1, '岗位':1}), Counter({'前端':1, '面试':1, '岗位':1})]

    print(bm25.score(["岗位"]))      
    # 两个文档都有“岗位”，分数相近

    print(bm25.score(["前端"]))      
    # 只命中文档2，文档1为0
