#include <algorithm>
#include <chrono>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <random>
#include <unordered_map>
#include <utility>
#include <vector>

using Clock = std::chrono::steady_clock;
enum EdgeState : unsigned char { free_edge, included, excluded };

struct Solver {
    int n, m;
    std::vector<std::pair<int,int>> ends;
    std::vector<std::vector<int>> incident;
    std::vector<std::uint64_t> edge_keys;
    std::mt19937_64 gen;
    Clock::time_point deadline;
    long long nodes = 0;
    bool timed_out = false;
    std::vector<int> route;

    int other(int edge, int u) const {
        return ends[edge].first ^ ends[edge].second ^ u;
    }

    int root(const std::vector<int>& parent, int v) const {
        while (parent[v] != v) v = parent[v];
        return v;
    }

    bool search(std::vector<EdgeState> status) {
        if ((nodes++ & 127) == 0 && Clock::now() >= deadline) timed_out = true;
        if (timed_out) return false;

        std::vector<int> parent(n), size(n), count(n), open(n);
        std::vector<int> discovered(n), parent_edge(n), order;
        std::vector<std::uint64_t> prefix(n), keys(m);
        order.reserve(n);
        for (;;) {
            std::iota(parent.begin(), parent.end(), 0);
            std::fill(size.begin(), size.end(), 1);
            std::fill(count.begin(), count.end(), 0);
            std::fill(open.begin(), open.end(), 0);
            int closing_edge = -1;
            for (int e = 0; e < m; ++e) {
                const auto [u, v] = ends[e];
                if (status[e] == free_edge) {
                    ++open[u];
                    ++open[v];
                } else if (status[e] == included) {
                    if (++count[u] > 2 || ++count[v] > 2) return false;
                    int a = root(parent, u);
                    int b = root(parent, v);
                    if (a == b) {
                        if (size[a] != n) return false;
                        closing_edge = e;
                    } else {
                        if (size[a] < size[b]) std::swap(a, b);
                        parent[b] = a;
                        size[a] += size[b];
                    }
                }
            }
            if (closing_edge >= 0) {
                int cur = 0, prev = -1;
                do {
                    route.push_back(cur);
                    int next = -1;
                    for (int e : incident[cur]) {
                        if (status[e] == included && other(e, cur) != prev) {
                            next = other(e, cur);
                            break;
                        }
                    }
                    prev = cur;
                    cur = next;
                } while (cur != 0);
                return true;
            }
            bool changed = false;
            for (int e = 0; e < m; ++e) {
                if (status[e] != free_edge) continue;
                const auto [u, v] = ends[e];
                const int a = root(parent, u);
                if (a == root(parent, v) && size[a] != n) {
                    status[e] = excluded;
                    --open[u];
                    --open[v];
                    changed = true;
                }
            }
            for (int u = 0; u < n; ++u) {
                if (count[u] + open[u] < 2) return false;
                if (!open[u]) continue;
                if (count[u] != 2 && count[u] + open[u] != 2) continue;
                for (int e : incident[u]) {
                    if (status[e] != free_edge) continue;
                    const int v = other(e, u);
                    status[e] = count[u] == 2 ? excluded : included;
                    if (status[e] == included && ++count[v] > 2) return false;
                    --open[v];
                    changed = true;
                }
            }
            if (changed) continue;

            // Find bridges and candidate two-edge cuts using a DFS cycle basis.
            std::fill(discovered.begin(), discovered.end(), -1);
            std::fill(prefix.begin(), prefix.end(), 0);
            order.clear();
            auto dfs = [&](auto&& self, int u, int pe) -> void {
                discovered[u] = static_cast<int>(order.size());
                parent_edge[u] = pe;
                order.push_back(u);
                for (int e : incident[u]) {
                    if (e == pe || status[e] == excluded) continue;
                    const int v = other(e, u);
                    if (discovered[v] < 0) {
                        self(self, v, e);
                    } else if (discovered[v] < discovered[u]) {
                        keys[e] = edge_keys[e];
                        prefix[u] ^= keys[e];
                        prefix[v] ^= keys[e];
                    }
                }
            };
            dfs(dfs, 0, -1);
            if (static_cast<int>(order.size()) != n) return false;
            for (auto it = order.rbegin(); it != order.rend(); ++it) {
                const int u = *it;
                const int e = parent_edge[u];
                if (e < 0) continue;
                keys[e] = prefix[u];
                if (keys[e] == 0) {
                    // A bridge gives a zero signature. Check the cut directly.
                    if (!connected_without(status, e, -1)) return false;
                }
                prefix[other(e, u)] ^= keys[e];
            }
            std::unordered_map<std::uint64_t, int> seen;
            seen.reserve(m);
            for (int e = 0; e < m; ++e) {
                if (status[e] == excluded) continue;
                const auto [it, inserted] = seen.emplace(keys[e], e);
                if (inserted) continue;
                const int f = it->second;
                if (status[e] == included && status[f] == included) continue;
                if (!connected_without(status, e, f)) {
                    status[e] = status[f] = included;
                    changed = true;
                }
            }
            if (!changed) break;
        }

        // Prefer an endpoint of an existing path with the fewest available choices.
        int chosen = -1;
        int best_open = n + 1;
        int best_count = -1;
        int tied = 0;
        for (int u = 0; u < n; ++u) {
            if (!open[u]) continue;
            if (count[u] > best_count || (count[u] == best_count && open[u] < best_open)) {
                chosen = u;
                best_count = count[u];
                best_open = open[u];
                tied = 1;
            } else if (count[u] == best_count && open[u] == best_open && gen() % ++tied == 0) {
                chosen = u;
            }
        }
        if (chosen < 0) return false;
        int branch = -1;
        tied = 0;
        for (int e : incident[chosen]) {
            if (status[e] == free_edge && gen() % ++tied == 0) branch = e;
        }
        if (branch < 0) return false;
        status[branch] = included;
        if (search(status)) return true;
        if (timed_out) return false;
        status[branch] = excluded;
        return search(std::move(status));
    }

    bool connected_without(const std::vector<EdgeState>& status, int a, int b) const {
        std::vector<int> seen(n, 0);
        std::vector<int> queue{0};
        queue.reserve(n);
        seen[0] = 1;
        for (size_t i = 0; i < queue.size(); ++i) {
            int u = queue[i];
            for (int e : incident[u]) {
                if (e == a || e == b || status[e] == excluded) continue;
                int v = other(e, u);
                if (seen[v] == 0) {
                    seen[v] = 1;
                    queue.push_back(v);
                }
            }
        }
        return static_cast<int>(queue.size()) == n;
    }
};

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    Solver s;
    s.gen.seed(std::stoull(argv[2]));
    if (!(std::cin >> s.n >> s.m)) return 2;
    s.incident.resize(s.n);
    for (int e = 0; e < s.m; ++e) {
        int u, v;
        if (!(std::cin >> u >> v)) return 2;
        s.ends.emplace_back(u, v);
        s.incident[u].push_back(e);
        s.incident[v].push_back(e);
        s.edge_keys.push_back(s.gen());
    }
    s.deadline = Clock::now() + std::chrono::milliseconds(std::stoll(argv[1]));
    if (s.search(std::vector<EdgeState>(s.m, free_edge))) {
        std::cout << "resuelto " << s.nodes << '\n';
        for (int u : s.route) std::cout << u << ' ';
        std::cout << '\n';
    } else {
        std::cout << (s.timed_out ? "agotado" : "sin_ciclo") << ' ' << s.nodes << '\n';
    }
}
