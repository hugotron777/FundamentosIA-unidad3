// Hamiltonian-cycle dynamic programming along an ordering with a small boundary.
// A state records the degree of each active vertex and the paired ends of
// every open path. An internal cycle is rejected until the last vertex.
#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <iostream>
#include <numeric>
#include <random>
#include <unordered_map>
#include <vector>

namespace {
using Clock = std::chrono::steady_clock;
using Key = std::uint64_t;
constexpr int max_boundary = 14;
constexpr std::size_t max_total_states = 2'000'000;
constexpr std::size_t max_layer_states = 110'000;

using Graph = std::vector<std::vector<int>>;

struct Ordering {
    std::vector<int> vertices;
    int width = 0;
    double score = 0.0;
};

std::vector<int> positions(const std::vector<int>& order) {
    std::vector<int> position(order.size());
    for (int i = 0; i < static_cast<int>(order.size()); ++i) position[order[i]] = i;
    return position;
}

std::vector<int> last_neighbor(const Graph& graph, const std::vector<int>& order) {
    const auto pos = positions(order);
    std::vector<int> last(order.size());
    for (int i = 0; i < static_cast<int>(order.size()); ++i) {
        last[i] = i;
        for (int v : graph[order[i]]) last[i] = std::max(last[i], pos[v]);
    }
    return last;
}

Ordering rate_order(const Graph& graph, std::vector<int> order) {
    const auto last = last_neighbor(graph, order);
    std::vector<int> ends(order.size(), 0);
    Ordering result{std::move(order)};
    for (int i = 0, width = 0; i < static_cast<int>(last.size()); ++i) {
        if (last[i] > i) {
            ++width;
            ++ends[last[i]];
        }
        width -= ends[i];
        result.width = std::max(result.width, width);
        result.score += std::ldexp(1.0, std::min(width, 40));
    }
    return result;
}

std::vector<int> breadth_first(const Graph& graph, int start, const std::vector<int>& anchor = {}) {
    std::vector<unsigned char> visited(graph.size(), 0);
    std::vector<int> order = anchor;
    order.reserve(graph.size());
    for (int v : anchor) visited[v] = 1;
    if (!visited[start]) {
        order.push_back(start);
        visited[start] = 1;
    }
    int next_start = 0;
    for (std::size_t i = anchor.size(); i < graph.size(); ++i) {
        if (i == order.size()) {
            if (anchor.empty()) break;
            while (visited[next_start]) ++next_start;
            order.push_back(next_start);
            visited[next_start] = 1;
        }
        for (int v : graph[order[i]]) {
            if (visited[v]) continue;
            visited[v] = 1;
            order.push_back(v);
        }
    }
    return order;
}

struct State {
    Key key;
    int previous;
    int first;
    int second;
};

int degree(int slot_value) {
    if (slot_value <= 1) return 2 * slot_value;
    return 1;
}

using Slots = std::array<int, max_boundary + 1>;

bool join(Slots& state, int left, int right, bool final_vertex) {
    const int l = state[left];
    const int r = state[right];
    if (l == 1 || r == 1) return false;
    if (l == right + 2) {
        if (!final_vertex) return false;
        state[left] = state[right] = 1;
        return true;
    }
    const int a = l == 0 ? left : l - 2;
    const int b = r == 0 ? right : r - 2;
    state[left] = l == 0 ? b + 2 : 1;
    state[right] = r == 0 ? a + 2 : 1;
    state[a] = b + 2;
    state[b] = a + 2;
    return true;
}

struct SearchResult {
    const char* status;
    std::vector<int> route;
};

SearchResult solve(const Graph& graph, const Ordering& ordering, Clock::time_point deadline) {
    const auto& order = ordering.vertices;
    const int n = static_cast<int>(order.size());
    const auto pos = positions(order);
    const auto last = last_neighbor(graph, order);
    std::vector<int> remaining(n);
    for (int vertex = 0; vertex < n; ++vertex) remaining[vertex] = graph[vertex].size();

    std::vector<std::vector<State>> layers(n + 1);
    layers[0].push_back({0, -1, -1, -1});
    std::vector<int> boundary;
    std::size_t states_seen = 1;
    for (int step = 0; step < n; ++step) {
        if (Clock::now() >= deadline) return {"agotado", {}};
        const int vertex = order[step];
        const int incoming = static_cast<int>(boundary.size());
        const bool final_vertex = step + 1 == n;
        Slots index_after{}, capacity{};
        std::vector<int> backward;
        for (int i = 0; i <= incoming; ++i) {
            const int v = i == incoming ? vertex : boundary[i];
            if (i < incoming && std::binary_search(graph[vertex].begin(), graph[vertex].end(), v)) {
                backward.push_back(i);
                --remaining[v];
                --remaining[vertex];
            }
            index_after[i] = -1;
        }

        std::vector<int> next_boundary;
        for (int i = 0; i <= incoming; ++i) {
            const int v = i == incoming ? vertex : boundary[i];
            capacity[i] = remaining[v];
            if (last[pos[v]] > step) {
                index_after[i] = static_cast<int>(next_boundary.size());
                next_boundary.push_back(v);
            }
        }

        auto& next_layer = layers[step + 1];
        const auto& current = layers[step];
        std::unordered_map<Key, int> seen;
        seen.reserve(std::min(max_layer_states, 2 * current.size() + 1));
        for (int state_id = 0; state_id < static_cast<int>(current.size()); ++state_id) {
            if ((state_id & 127) == 0 && Clock::now() >= deadline) return {"agotado", {}};
            Slots original{};
            auto key = current[state_id].key;
            for (int i = 0; i < incoming; ++i) {
                original[i] = static_cast<int>(key & 15);
                key >>= 4;
            }
            const auto advance = [&](int a, int b) {
                Slots partial = original;
                if (a >= 0 && !join(partial, a, incoming, final_vertex)) return;
                if (b >= 0 && !join(partial, b, incoming, final_vertex)) return;
                Key next_key = 0;
                for (int i = 0; i <= incoming; ++i) {
                    const int val = partial[i];
                    if (degree(val) + capacity[i] < 2) return;
                    if (index_after[i] < 0) continue;
                    const int encoded = val < 2 ? val : index_after[val - 2] + 2;
                    next_key |= static_cast<Key>(encoded) << (4 * index_after[i]);
                }
                if (seen.emplace(next_key, 0).second) {
                    next_layer.push_back({next_key, state_id, a < 0 ? -1 : boundary[a], b < 0 ? -1 : boundary[b]});
                }
            };

            if (capacity[incoming] >= 2) advance(-1, -1);
            for (std::size_t a = 0; a < backward.size(); ++a) {
                if (original[backward[a]] == 1) continue;
                if (capacity[incoming] >= 1) advance(backward[a], -1);
                for (std::size_t b = a + 1; b < backward.size(); ++b) {
                    if (original[backward[b]] != 1) advance(backward[a], backward[b]);
                }
            }
            if (next_layer.size() > max_layer_states) return {"limite_estados", {}};
        }
        if (next_layer.empty()) return {"sin_ciclo", {}};
        states_seen += next_layer.size();
        if (states_seen > max_total_states) return {"limite_estados", {}};
        boundary = std::move(next_boundary);
    }

    Graph cycle(n);
    int id = 0;
    for (int step = n; step > 0; --step) {
        const auto& entry = layers[step][id];
        const int vertex = order[step - 1];
        for (int neighbor : {entry.first, entry.second}) {
            if (neighbor < 0) continue;
            cycle[vertex].push_back(neighbor);
            cycle[neighbor].push_back(vertex);
        }
        id = entry.previous;
    }
    std::vector<int> route;
    int last_vertex = -1;
    int current_vertex = 0;
    for (int i = 0; i < n; ++i) {
        if (cycle[current_vertex].size() != 2) return {"error_reconstruccion", {}};
        route.push_back(current_vertex);
        int next = cycle[current_vertex][0];
        if (next == last_vertex) next = cycle[current_vertex][1];
        last_vertex = current_vertex;
        current_vertex = next;
        if (current_vertex == 0 && i + 1 != n) return {"error_subciclo", {}};
    }
    if (current_vertex != 0) return {"error_reconstruccion", {}};
    return {"resuelto", std::move(route)};
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

    std::vector<Ordering> choices;
#ifdef FHCP_VERTICES_DOMINANTES
    std::vector<int> degree_order(n);
    std::iota(degree_order.begin(), degree_order.end(), 0);
    std::stable_sort(degree_order.begin(), degree_order.end(), [&](int u, int v) {
        return graph[u].size() > graph[v].size();
    });
    for (int count : {1, 2, 4, 8}) {
        if (count >= n || graph[degree_order[count - 1]].size() < 10) break;
        const std::vector<int> anchor(degree_order.begin(), degree_order.begin() + count);
        for (int attempt = 0; attempt < 12 && Clock::now() < deadline; ++attempt) {
            auto order = breadth_first(graph, gen() % n, anchor);
            choices.push_back(rate_order(graph, order));
            std::reverse(order.begin(), order.end());
            choices.push_back(rate_order(graph, std::move(order)));
        }
    }
    if (choices.empty()) {
        std::cout << "sin_vertices_dominantes\n";
        return 0;
    }
#else
    int endpoint = gen() % n;
    for (int attempt = 0; attempt < 16; ++attempt) {
        int start = attempt < 4 ? endpoint : gen() % n;
        auto order = breadth_first(graph, start);
        if (static_cast<int>(order.size()) != n) {
            std::cout << "desconectado\n";
            return 0;
        }
        endpoint = order.back();
        choices.push_back(rate_order(graph, order));
        std::reverse(order.begin(), order.end());
        choices.push_back(rate_order(graph, std::move(order)));
    }
#endif
    std::sort(choices.begin(), choices.end(), [](const Ordering& a, const Ordering& b) {
        return a.score < b.score;
    });
    int attempts = 0;
    const char* status = "frontera_ancha";
    for (const auto& order : choices) {
        if (order.width > max_boundary) continue;
        if (++attempts > 4) break;
        auto result = solve(graph, order, deadline);
        status = result.status;
        if (!result.route.empty()) {
            std::cout << "resuelto " << order.width << '\n';
            for (int vertex : result.route) std::cout << vertex << ' ';
            std::cout << '\n';
            return 0;
        }
        if (Clock::now() >= deadline) break;
    }
    std::cout << status << '\n';
}
