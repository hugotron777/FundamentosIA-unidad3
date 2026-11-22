// Searches for a 2-vertex cut with two nontrivial sides. For each sampled
// vertex u, articulation points in G-u give candidate second vertices.
#include <algorithm>
#include <chrono>
#include <iostream>
#include <numeric>
#include <random>
#include <vector>

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    using Clock = std::chrono::steady_clock;
    const auto deadline = Clock::now() + std::chrono::milliseconds(std::stoll(argv[1]));
    std::mt19937 gen(std::stoul(argv[2]));
    int n, m;
    if (!(std::cin >> n >> m) || n < 3 || m < 0) return 2;
    std::vector<std::vector<int>> graph(n);
    for (int i = 0; i < m; ++i) {
        int u, v;
        if (!(std::cin >> u >> v) || u < 0 || v < 0 || u >= n || v >= n || u == v) return 2;
        graph[u].push_back(v);
        graph[v].push_back(u);
    }

    std::vector<int> candidates(n);
    std::iota(candidates.begin(), candidates.end(), 0);
    std::shuffle(candidates.begin(), candidates.end(), gen);
    const auto by_degree = [&](int a, int b) { return graph[a].size() > graph[b].size(); };
    std::partial_sort(candidates.begin(), candidates.begin() + std::min(20, n), candidates.end(), by_degree);
    std::vector<int> seen(n), low(n), size(n), detached(n), parts(n);
    int best = 0, first = -1, second = -1;
    for (int i = 0; i < std::min(300, n) && Clock::now() < deadline; ++i) {
        const int removed = candidates[i], root = removed == 0 ? 1 : 0;
        std::fill(seen.begin(), seen.end(), -1);
        std::fill(detached.begin(), detached.end(), 0);
        std::fill(parts.begin(), parts.end(), 0);
        int step = 0;
        const auto dfs = [&](auto&& self, int vertex, int parent) -> void {
            seen[vertex] = low[vertex] = step++;
            size[vertex] = 1;
            for (int next : graph[vertex]) {
                if (next == parent || next == removed) continue;
                if (seen[next] >= 0) {
                    low[vertex] = std::min(low[vertex], seen[next]);
                    continue;
                }
                self(self, next, vertex);
                size[vertex] += size[next];
                low[vertex] = std::min(low[vertex], low[next]);
                if (low[next] >= seen[vertex]) {
                    ++parts[vertex];
                    if (detached[vertex] == 0) detached[vertex] = size[next];
                }
            }
        };
        dfs(dfs, root, -1);
        if (step != n - 1) continue;
        for (int v = 0; v < n; ++v) {
            if (v == removed || parts[v] != (v == root ? 2 : 1)) continue;
            const int balance = std::min(detached[v], n - 2 - detached[v]);
            if (balance < 8 || balance <= best) continue;
            best = balance;
            first = removed;
            second = v;
        }
        if (best >= n / 3) break;
    }
    std::cout << first << ' ' << second << '\n';
}
