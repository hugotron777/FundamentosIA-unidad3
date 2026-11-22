// Hamiltonian-cycle dynamic programming on the bags of a vertex elimination.
// Each separator records used degrees and which open path ends are paired.
#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <functional>
#include <iostream>
#include <numeric>
#include <queue>
#include <random>
#include <tuple>
#include <unordered_set>
#include <utility>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
#ifdef FHCP_FRONTERA_AMPLIA
using Key = __uint128_t;
constexpr int max_separator = 21;
constexpr int bits_per_slot = 5;
#else
using Key = std::uint64_t;
constexpr int max_separator = 13;
constexpr int bits_per_slot = 4;
#endif
constexpr int max_bag = max_separator + 1;
constexpr Key closed_bit = Key{1} << (bits_per_slot * max_bag);
constexpr Key slot_mask = (Key{1} << bits_per_slot) - 1;
constexpr std::size_t max_states = 2'000'000;
constexpr std::size_t max_stage = 100'000;

struct KeyHash {
    std::size_t operator()(Key key) const noexcept {
        const auto low = static_cast<std::uint64_t>(key);
#ifdef FHCP_FRONTERA_AMPLIA
        const auto high = static_cast<std::uint64_t>(key >> 64);
        return std::hash<std::uint64_t>{}(low ^ (high + 0x9e3779b97f4a7c15ULL + (low << 6) + (low >> 2)));
#else
        return std::hash<std::uint64_t>{}(low);
#endif
    }
};

using Graph = std::vector<std::vector<int>>;
using Slots = std::array<int, max_bag>;

struct Bag {
    int vertex;
    std::vector<int> separator;
    std::vector<int> children;
};

std::vector<Bag> decompose(const Graph& graph, std::mt19937& gen, Clock::time_point deadline, bool min_fill) {
    const int n = static_cast<int>(graph.size());
    std::vector<std::unordered_set<int>> active(n);
    std::vector<int> rank(n), index(n, -1);
    std::iota(rank.begin(), rank.end(), 0);
    std::shuffle(rank.begin(), rank.end(), gen);
    std::vector<int> generation(n, 0);
    using Entry = std::tuple<int, int, int, int, int>;
    std::priority_queue<Entry, std::vector<Entry>, std::greater<Entry>> queue;
    for (int v = 0; v < n; ++v) {
        active[v].insert(graph[v].begin(), graph[v].end());
    }
    const auto offer = [&](int v) {
        ++generation[v];
        const int degree = static_cast<int>(active[v].size());
        if (degree > max_separator || index[v] >= 0) return;
        int fill = 0;
        if (min_fill) {
            for (int a : active[v]) {
                for (int b : active[v]) {
                    if (a < b && active[a].count(b) == 0) ++fill;
                }
            }
        }
        queue.emplace(min_fill ? fill : degree, degree, rank[v], v, generation[v]);
    };
    for (int v = 0; v < n; ++v) offer(v);

    std::vector<Bag> bags;
    bags.reserve(n);
    std::vector<int> dirty_stamp(n, -1);
    while (!queue.empty() && static_cast<int>(bags.size()) < n && Clock::now() < deadline) {
        const auto [score, degree, priority, u, stamp] = queue.top();
        queue.pop();
        if (index[u] >= 0 || stamp != generation[u]) continue;
        index[u] = static_cast<int>(bags.size());
        auto& bag = bags.emplace_back(Bag{u, {active[u].begin(), active[u].end()}, {}});
        std::sort(bag.separator.begin(), bag.separator.end());
        for (int v : bag.separator) {
            active[v].erase(u);
            for (int w : bag.separator) {
                if (v != w) active[v].insert(w);
            }
        }
        active[u].clear();
        for (int v : bag.separator) {
            if (dirty_stamp[v] != index[u]) {
                dirty_stamp[v] = index[u];
                offer(v);
            }
            if (!min_fill) continue;
            for (int w : active[v]) {
                if (dirty_stamp[w] == index[u] || active[w].size() > max_separator) continue;
                dirty_stamp[w] = index[u];
                offer(w);
            }
        }
    }
    if (static_cast<int>(bags.size()) != n) return {};
    for (int i = 0; i + 1 < n; ++i) {
        int parent = n;
        for (int v : bags[i].separator) parent = std::min(parent, index[v]);
        if (parent == n) return {};
        bags[parent].children.push_back(i);
    }
    return bags;
}

struct Configuration {
    Slots slots{};
    bool closed = false;
};

Configuration unpack(Key key, int size) {
    Configuration result;
    result.closed = (key & closed_bit) != 0;
    for (int i = 0; i < size; ++i) {
        result.slots[i] = static_cast<int>(key & slot_mask);
        key >>= bits_per_slot;
    }
    return result;
}

Key pack(const Configuration& config, int start, int end) {
    Key key = config.closed ? closed_bit : 0;
    for (int i = start; i < end; ++i) {
        const int value = config.slots[i];
        key |= static_cast<Key>(value < 2 ? value : value - start) << (bits_per_slot * (i - start));
    }
    return key;
}

bool join(Configuration& config, int u, int v) {
    auto& slots = config.slots;
    const int left = slots[u], right = slots[v];
    if (config.closed || left == 1 || right == 1) return false;
    if (left == v + 2) {
        slots[u] = slots[v] = 1;
        if (std::any_of(slots.begin(), slots.end(), [](int value) { return value > 1; })) return false;
        config.closed = true;
        return true;
    }
    const int a = left == 0 ? u : left - 2;
    const int b = right == 0 ? v : right - 2;
    if (left != 0) slots[u] = 1;
    if (right != 0) slots[v] = 1;
    slots[a] = b + 2;
    slots[b] = a + 2;
    return true;
}

bool combine(Configuration& base, Key incoming, const std::vector<int>& mapping) {
    const auto child = unpack(incoming, static_cast<int>(mapping.size()));
    if (base.closed) return false;
    if (child.closed && std::any_of(base.slots.begin(), base.slots.end(), [](int v) { return v != 0; })) {
        return false;
    }
    for (int i = 0; i < static_cast<int>(mapping.size()); ++i) {
        if (child.slots[i] == 1) {
            if (base.slots[mapping[i]] != 0) return false;
            base.slots[mapping[i]] = 1;
        }
    }
    for (int i = 0; i < static_cast<int>(mapping.size()); ++i) {
        const int partner = child.slots[i] - 2;
        if (partner > i && !join(base, mapping[i], mapping[partner])) return false;
    }
    base.closed = base.closed || child.closed;
    return true;
}

struct Combined {
    Key key;
    int before;
    int child_state;
};

struct Selected {
    Key key;
    int combined;
    int first;
    int second;
};

struct Trace {
    std::vector<std::vector<Combined>> merges;
    std::vector<Selected> output;
};

std::vector<int> reconstruct(const std::vector<Bag>& bags, const std::vector<Trace>& traces) {
    Graph cycle(bags.size());
    std::vector<std::pair<int, int>> todo{{static_cast<int>(bags.size()) - 1, 0}};
    while (!todo.empty()) {
        const auto [index, state] = todo.back();
        todo.pop_back();
        const auto& bag = bags[index];
        const auto& trace = traces[index];
        const auto& selected = trace.output[state];
        for (int v : {selected.first, selected.second}) {
            if (v < 0) continue;
            cycle[bag.vertex].push_back(v);
            cycle[v].push_back(bag.vertex);
        }
        int config = selected.combined;
        for (int i = static_cast<int>(bag.children.size()) - 1; i >= 0; --i) {
            const auto& merge = trace.merges[i + 1][config];
            todo.emplace_back(bag.children[i], merge.child_state);
            config = merge.before;
        }
    }

    std::vector<int> route;
    int previous = -1, vertex = 0;
    for (std::size_t i = 0; i < bags.size(); ++i) {
        if (cycle[vertex].size() != 2) return {};
        route.push_back(vertex);
        const int next = cycle[vertex][0] == previous ? cycle[vertex][1] : cycle[vertex][0];
        previous = vertex;
        vertex = next;
        if (vertex == 0 && i + 1 != bags.size()) return {};
    }
    if (vertex != 0) return {};
    return route;
}

struct Result {
    const char* status;
    std::vector<int> route;
};

Result solve(const Graph& graph, const std::vector<Bag>& bags, Clock::time_point deadline) {
    std::vector<Trace> traces(bags.size());
    std::size_t states = 0;
    for (std::size_t i = 0; i < bags.size(); ++i) {
        if (Clock::now() >= deadline) return {"agotado", {}};
        const auto& bag = bags[i];
        auto& trace = traces[i];
        const int size = static_cast<int>(bag.separator.size()) + 1;
        trace.merges.reserve(bag.children.size() + 1);
        trace.merges.push_back({{0, -1, -1}});
        for (int child : bag.children) {
            std::vector<int> mapping;
            for (int v : bags[child].separator) {
                if (v == bag.vertex) {
                    mapping.push_back(0);
                } else {
                    const auto it = std::lower_bound(bag.separator.begin(), bag.separator.end(), v);
                    if (it == bag.separator.end() || *it != v) return {"error_separador", {}};
                    mapping.push_back(static_cast<int>(it - bag.separator.begin()) + 1);
                }
            }
            const auto& input = traces[child].output;
            const auto& current = trace.merges.back();
            std::vector<Combined> merged;
            std::unordered_set<Key, KeyHash> seen;
            std::size_t pairs = 0;
            for (int a = 0; a < static_cast<int>(current.size()); ++a) {
                const auto base = unpack(current[a].key, size);
                for (int b = 0; b < static_cast<int>(input.size()); ++b) {
                    if ((pairs++ & 2047) == 0 && Clock::now() >= deadline) return {"agotado", {}};
                    auto config = base;
                    if (!combine(config, input[b].key, mapping)) continue;
                    const Key key = pack(config, 0, size);
                    if (seen.insert(key).second) merged.push_back({key, a, b});
                    if (merged.size() > max_stage) return {"limite_estados", {}};
                }
            }
            if (merged.empty()) return {"sin_ciclo", {}};
            states += merged.size();
            if (states > max_states) return {"limite_estados", {}};
            trace.merges.push_back(std::move(merged));
        }

        std::vector<int> real_neighbors;
        for (int j = 1; j < size; ++j) {
            if (std::binary_search(graph[bag.vertex].begin(), graph[bag.vertex].end(), bag.separator[j - 1])) {
                real_neighbors.push_back(j);
            }
        }

        const auto& current = trace.merges.back();
        std::unordered_set<Key, KeyHash> seen;
        for (int a = 0; a < static_cast<int>(current.size()); ++a) {
            if ((a & 255) == 0 && Clock::now() >= deadline) return {"agotado", {}};
            const auto base = unpack(current[a].key, size);
            const auto add = [&](int first, int second) {
                auto config = base;
                if (first >= 0 && !join(config, 0, first)) return;
                if (second >= 0 && !join(config, 0, second)) return;
                if (size == 1 && !config.closed) return;
                const Key key = pack(config, 1, size);
                if (seen.insert(key).second) trace.output.push_back({
                    key, a, first < 0 ? -1 : bag.separator[first - 1], second < 0 ? -1 : bag.separator[second - 1],
                });
            };
            if (base.slots[0] == 1) {
                add(-1, -1);
            } else if (base.slots[0] == 0) {
                for (std::size_t j = 0; j < real_neighbors.size(); ++j) {
                    for (std::size_t k = j + 1; k < real_neighbors.size(); ++k) {
                        add(real_neighbors[j], real_neighbors[k]);
                    }
                }
            } else {
                for (int neighbor : real_neighbors) add(neighbor, -1);
            }
            if (trace.output.size() > max_stage) return {"limite_estados", {}};
        }
        if (trace.output.empty()) return {"sin_ciclo", {}};
        states += trace.output.size();
        if (states > max_states) return {"limite_estados", {}};
    }

    auto route = reconstruct(bags, traces);
    return {route.empty() ? "error_reconstruccion" : "resuelto", std::move(route)};
}
}  // namespace

int main(int argc, char** argv) {
    if (argc != 3) return 2;
    const auto deadline = Clock::now() + std::chrono::milliseconds(std::stoll(argv[1]));
    std::mt19937 gen(std::stoul(argv[2]));
    int n, m;
    if (!(std::cin >> n >> m) || n < 3 || m < 0) return 2;
    Graph graph(n);
    for (int i = 0; i < m; ++i) {
        int u, v;
        if (!(std::cin >> u >> v) || u < 0 || v < 0 || u >= n || v >= n || u == v) return 2;
        graph[u].push_back(v);
        graph[v].push_back(u);
    }
    for (auto& neighbors : graph) std::sort(neighbors.begin(), neighbors.end());

    const char* status = "separador_ancho";
    for (int attempt = 0; attempt < 4 && Clock::now() < deadline; ++attempt) {
        const auto bags = decompose(graph, gen, deadline, attempt % 2 == 0);
        if (bags.empty()) continue;
        auto result = solve(graph, bags, deadline);
        status = result.status;
        if (!result.route.empty()) {
            std::cout << "resuelto\n";
            for (int vertex : result.route) std::cout << vertex << ' ';
            std::cout << '\n';
            return 0;
        }
        if (std::string(status) == "sin_ciclo") break;
    }
    std::cout << status << '\n';
}
