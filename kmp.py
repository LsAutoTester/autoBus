def kmp_search(text, pattern):
    def compute_prefix_function(pattern):
        m = len(pattern)
        pi = [0] * m
        j = 0
        print(pi)
        for i in range(1, m):
            print(i)
            while j > 0 and pattern[j] != pattern[i]:
                j = pi[j - 1]
            if pattern[j] == pattern[i]:
                j += 1
            pi[i] = j
        print(pi)
        return pi

    n, m = len(text), len(pattern)
    if m == 0:
        return 0
    pi = compute_prefix_function(pattern)
    j = 0
    for i in range(n):
        print(i)
        while j > 0 and pattern[j] != text[i]:
            j = pi[j - 1]
        if pattern[j] == text[i]:
            j += 1
        if j == m:
            return i - m + 1
    return -1


# 示例
text = "ABABDABACDABABCABABABABDABACDABABCABAB"
pattern = "ABABCABAB"
result = kmp_search(text, pattern)
print("模式串在文本串中的起始位置：", result)
