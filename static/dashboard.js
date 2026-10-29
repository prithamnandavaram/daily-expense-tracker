/**
 * dashboard.js — Interactive Client-Side Engine for MovieLens Analytics
 * DS5003 Data Engineering Lab • IIT Palakkad
 */

// Color Palettes
const PALETTE = [
  '#7c5cff', '#00e5a3', '#ff5376', '#ffb72b', '#00c0f0',
  '#e056fd', '#2ed573', '#ffa502', '#ff4757', '#1e90ff',
  '#3742fa', '#70a1ff', '#2ed573', '#5352ed', '#ff6348',
  '#1dd1a1', '#10ac84', '#ee5253', '#0abde3', '#48dbfb'
];

// Chart Instances Store
const charts = {
  a: null,
  b: null,
  d: null,
  e: null,
  f: null,
  g: null,
};

let currentMovieId = null;

// Global Chart.js Styling Defaults
Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
Chart.defaults.color = '#8a94a6';
Chart.defaults.borderColor = '#232a3d';
Chart.defaults.plugins.tooltip.backgroundColor = '#161b28';
Chart.defaults.plugins.tooltip.borderColor = '#323b54';
Chart.defaults.plugins.tooltip.borderWidth = 1;
Chart.defaults.plugins.tooltip.padding = 10;
Chart.defaults.plugins.tooltip.cornerRadius = 8;
Chart.defaults.plugins.tooltip.titleColor = '#ffffff';
Chart.defaults.plugins.tooltip.bodyColor = '#8a94a6';

// --------------------------------------------------------------------------
// API Client Helper
// --------------------------------------------------------------------------
async function fetchAPI(endpoint) {
  try {
    const res = await fetch(endpoint);
    if (res.status === 401) {
      window.location.href = '/login';
      return null;
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    return null;
  }
}

// --------------------------------------------------------------------------
// Question (a): Top-5 Tags by Relevance Scores
// --------------------------------------------------------------------------
async function renderChartA(movieId) {
  const data = await fetchAPI(`/api/tags/top/${movieId}`);
  const canvas = document.getElementById('chartA');
  const emptyState = document.getElementById('emptyStateA');
  const subtitle = document.getElementById('tagSubtitle');

  if (!data || !data.tags || data.tags.length === 0) {
    if (charts.a) charts.a.destroy();
    emptyState.style.display = 'flex';
    subtitle.textContent = data?.title ? `No genome scores for "${data.title}"` : 'Selected Movie Genome';
    return;
  }

  emptyState.style.display = 'none';
  subtitle.textContent = `Top genome tags for "${data.title}"`;

  const labels = data.tags.map(t => t.tag);
  const scores = data.tags.map(t => t.relevance);

  if (charts.a) charts.a.destroy();

  charts.a = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Relevance Score',
        data: scores,
        backgroundColor: [
          'rgba(124, 92, 255, 0.85)',
          'rgba(124, 92, 255, 0.70)',
          'rgba(124, 92, 255, 0.55)',
          'rgba(124, 92, 255, 0.40)',
          'rgba(124, 92, 255, 0.30)',
        ],
        borderColor: '#7c5cff',
        borderWidth: 1.5,
        borderRadius: 6,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` Relevance: ${ctx.parsed.x.toFixed(4)}`
          }
        }
      },
      scales: {
        x: {
          min: 0,
          max: 1.0,
          grid: { color: 'rgba(35, 42, 61, 0.6)' },
          ticks: { color: '#8a94a6' }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#f0f3fa', font: { weight: 600 } }
        }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Question (d): Rating Distribution for Selected Movie
// --------------------------------------------------------------------------
async function renderChartD(movieId) {
  const data = await fetchAPI(`/api/ratings/distribution/${movieId}`);
  const canvas = document.getElementById('chartD');
  const emptyState = document.getElementById('emptyStateD');
  const subtitle = document.getElementById('distSubtitle');

  if (!data || !data.distribution) {
    if (charts.d) charts.d.destroy();
    emptyState.style.display = 'flex';
    return;
  }

  emptyState.style.display = 'none';
  subtitle.textContent = `${data.ratingCount.toLocaleString()} total reviews • Avg ${data.avgRating} ★`;

  // Update selected movie banner
  updateMovieBanner(data);

  const labels = data.distribution.map(d => d.label);
  const counts = data.distribution.map(d => d.count);

  if (charts.d) charts.d.destroy();

  charts.d = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Votes Count',
        data: counts,
        backgroundColor: 'rgba(0, 229, 163, 0.75)',
        borderColor: '#00e5a3',
        borderWidth: 1.5,
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.y.toLocaleString()} votes`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#f0f3fa', font: { weight: 600 } }
        },
        y: {
          grid: { color: 'rgba(35, 42, 61, 0.6)' },
          ticks: {
            color: '#8a94a6',
            callback: (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v
          }
        }
      }
    }
  });
}

function updateMovieBanner(data) {
  currentMovieId = data.movieId;
  const banner = document.getElementById('selectedMovieBanner');
  banner.style.display = 'flex';

  document.getElementById('bannerTitle').textContent = data.title;
  document.getElementById('bannerYear').textContent = data.year || 'N/A';
  document.getElementById('bannerSub').innerHTML = `
    ID: #${data.movieId} • Avg Rating: <span class="highlight-text font-bold">${data.avgRating} ★</span>
    (${data.ratingCount.toLocaleString()} ratings)
  `;

  // Update rating dropdown if user rated
  if (data.userRating) {
    document.getElementById('userRatingSelect').value = parseFloat(data.userRating).toFixed(1);
    document.getElementById('ratingStatusMsg').textContent = `Your saved rating: ${data.userRating} ★`;
  } else {
    document.getElementById('ratingStatusMsg').textContent = '';
  }
}

// --------------------------------------------------------------------------
// Question (b): Top 10 Movies by Average Rating
// --------------------------------------------------------------------------
async function renderChartB() {
  const year = document.getElementById('yearFilterB').value;
  const url = year ? `/api/movies/top_rated?year=${year}` : '/api/movies/top_rated';
  const movies = await fetchAPI(url);
  const canvas = document.getElementById('chartB');

  if (!movies || movies.length === 0) return;

  const labels = movies.map(m => m.year ? `${m.title} (${m.year})` : m.title);
  const ratings = movies.map(m => m.avgRating);
  const reviewCounts = movies.map(m => m.ratingCount);

  if (charts.b) charts.b.destroy();

  charts.b = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Average Rating (★)',
        data: ratings,
        backgroundColor: 'rgba(124, 92, 255, 0.75)',
        borderColor: '#7c5cff',
        borderWidth: 1.5,
        borderRadius: 6,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` Rating: ${ctx.parsed.x} ★ (${reviewCounts[ctx.dataIndex].toLocaleString()} reviews)`
          }
        }
      },
      scales: {
        x: {
          min: 3.5,
          max: 5.0,
          grid: { color: 'rgba(35, 42, 61, 0.6)' },
          ticks: { color: '#8a94a6' }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#f0f3fa', font: { weight: 600 } }
        }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Question (c): Most Popular Tag Given for Each Genre
// --------------------------------------------------------------------------
async function renderTableC() {
  const data = await fetchAPI('/api/tags/genre');
  const tbody = document.getElementById('genreTagsBody');
  if (!data || data.length === 0) {
    tbody.innerHTML = `<tr><td colspan="3" class="text-center text-muted">No tag data available</td></tr>`;
    return;
  }

  tbody.innerHTML = data.map(item => `
    <tr>
      <td><strong>${item.genre}</strong></td>
      <td><span class="section-badge font-mono" style="font-size: 0.85rem;">#${item.topTag}</span></td>
      <td style="text-align: right;" class="font-mono text-muted">${item.count.toLocaleString()}</td>
    </tr>
  `).join('');
}

// --------------------------------------------------------------------------
// Question (e): Distribution of Total Ratings for Movies
// --------------------------------------------------------------------------
async function renderChartE() {
  const data = await fetchAPI('/api/ratings/total_distribution');
  const canvas = document.getElementById('chartE');
  if (!data || data.length === 0) return;

  const labels = data.map(d => d.range);
  const counts = data.map(d => d.count);

  if (charts.e) charts.e.destroy();

  charts.e = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: 'Number of Movies',
        data: counts,
        backgroundColor: 'rgba(255, 183, 43, 0.75)',
        borderColor: '#ffb72b',
        borderWidth: 1.5,
        borderRadius: 6,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.y.toLocaleString()} movies in this review bracket`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#f0f3fa', font: { size: 11 } }
        },
        y: {
          grid: { color: 'rgba(35, 42, 61, 0.6)' },
          ticks: {
            color: '#8a94a6',
            callback: (v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v
          }
        }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Question (f): Genre Releases for Selected Year
// --------------------------------------------------------------------------
async function renderChartF() {
  const year = document.getElementById('yearFilterF').value;
  if (!year) return;

  const data = await fetchAPI(`/api/genres/releases?year=${year}`);
  const canvas = document.getElementById('chartF');
  if (!data || !data.releases || data.releases.length === 0) return;

  const labels = data.releases.map(r => r.genre);
  const counts = data.releases.map(r => r.count);

  if (charts.f) charts.f.destroy();

  charts.f = new Chart(canvas, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        label: `Releases in ${year}`,
        data: counts,
        backgroundColor: 'rgba(0, 192, 240, 0.75)',
        borderColor: '#00c0f0',
        borderWidth: 1.5,
        borderRadius: 6,
      }]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.parsed.x.toLocaleString()} titles released in ${year}`
          }
        }
      },
      scales: {
        x: {
          grid: { color: 'rgba(35, 42, 61, 0.6)' },
          ticks: { color: '#8a94a6' }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#f0f3fa', font: { weight: 600 } }
        }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Question (g): Genre-wise Coverage of Movies
// --------------------------------------------------------------------------
async function renderChartG() {
  const data = await fetchAPI('/api/genres/coverage');
  const canvas = document.getElementById('chartG');
  if (!data || data.length === 0) return;

  const labels = data.map(d => d.genre);
  const counts = data.map(d => d.count);

  if (charts.g) charts.g.destroy();

  charts.g = new Chart(canvas, {
    type: 'doughnut',
    data: {
      labels: labels,
      datasets: [{
        data: counts,
        backgroundColor: PALETTE.slice(0, labels.length),
        borderColor: '#161b28',
        borderWidth: 2,
        hoverOffset: 8,
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: {
          position: 'right',
          labels: {
            color: '#f0f3fa',
            font: { size: 11 },
            boxWidth: 14,
            padding: 10
          }
        },
        tooltip: {
          callbacks: {
            label: (ctx) => ` ${ctx.label}: ${ctx.parsed.toLocaleString()} movies (${((ctx.parsed / counts.reduce((a, b) => a + b, 0)) * 100).toFixed(1)}%)`
          }
        }
      }
    }
  });
}

// --------------------------------------------------------------------------
// Search & Autocomplete
// --------------------------------------------------------------------------
function setupSearch() {
  const searchInput = document.getElementById('movieSearch');
  const dropdown = document.getElementById('searchResults');
  const clearBtn = document.getElementById('clearSearchBtn');
  let debounceTimeout = null;

  searchInput.addEventListener('input', () => {
    const q = searchInput.value.trim();
    clearBtn.style.display = q.length > 0 ? 'block' : 'none';

    clearTimeout(debounceTimeout);
    if (q.length < 2) {
      dropdown.style.display = 'none';
      return;
    }

    debounceTimeout = setTimeout(async () => {
      const results = await fetchAPI(`/api/movies/search?q=${encodeURIComponent(q)}`);
      if (!results || results.length === 0) {
        dropdown.innerHTML = `<div class="search-item text-muted">No matching movies found</div>`;
        dropdown.style.display = 'block';
        return;
      }

      dropdown.innerHTML = results.map(m => `
        <div class="search-item" data-id="${m.movieId}" data-title="${m.title}">
          <span class="search-item-title">${m.title} ${m.year ? `(${m.year})` : ''}</span>
          <span class="search-item-meta">${m.avgRating ? `${m.avgRating} ★` : ''} • #${m.movieId}</span>
        </div>
      `).join('');
      dropdown.style.display = 'block';
    }, 250);
  });

  dropdown.addEventListener('click', (e) => {
    const item = e.target.closest('.search-item');
    if (!item || !item.dataset.id) return;

    const movieId = parseInt(item.dataset.id);
    searchInput.value = item.dataset.title;
    dropdown.style.display = 'none';

    loadMovie(movieId);
  });

  clearBtn.addEventListener('click', () => {
    searchInput.value = '';
    clearBtn.style.display = 'none';
    dropdown.style.display = 'none';
  });

  document.addEventListener('click', (e) => {
    if (!e.target.closest('.search-box-wrapper')) {
      dropdown.style.display = 'none';
    }
  });
}

function loadMovie(movieId) {
  renderChartA(movieId);
  renderChartD(movieId);
}

// --------------------------------------------------------------------------
// Interactive User Rating Submission (Regulation 4)
// --------------------------------------------------------------------------
function setupRatingSubmission() {
  const submitBtn = document.getElementById('submitRatingBtn');
  const select = document.getElementById('userRatingSelect');
  const statusMsg = document.getElementById('ratingStatusMsg');

  submitBtn.addEventListener('click', async () => {
    if (!currentMovieId) return;

    const ratingVal = parseFloat(select.value);
    submitBtn.disabled = true;
    submitBtn.textContent = 'Submitting...';

    try {
      const res = await fetch('/api/ratings/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ movieId: currentMovieId, rating: ratingVal })
      }).then(r => r.json());

      if (res.ok) {
        statusMsg.textContent = res.message;
        statusMsg.style.color = '#00e5a3';
        // Refresh rating distribution and overall top rated
        renderChartD(currentMovieId);
        renderChartB();
      } else {
        statusMsg.textContent = res.error || 'Failed to submit rating';
        statusMsg.style.color = '#ff5376';
      }
    } catch (err) {
      statusMsg.textContent = 'Network error while submitting rating';
      statusMsg.style.color = '#ff5376';
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = 'Submit Rating';
    }
  });
}

// --------------------------------------------------------------------------
// Populate Filter Selectors
// --------------------------------------------------------------------------
async function populateYears() {
  const years = await fetchAPI('/api/years');
  if (!years || years.length === 0) return;

  const selectB = document.getElementById('yearFilterB');
  const selectF = document.getElementById('yearFilterF');

  const optionsHTML = years.map(y => `<option value="${y}">${y}</option>`).join('');

  selectB.innerHTML = `<option value="">Overall (All Time)</option>` + optionsHTML;
  selectF.innerHTML = optionsHTML;

  // Set default year for F to 1995 (a landmark cinematic year in the dataset)
  if (years.includes(1995)) {
    selectF.value = 1995;
  }

  selectB.addEventListener('change', renderChartB);
  selectF.addEventListener('change', renderChartF);
}

// --------------------------------------------------------------------------
// Initialization
// --------------------------------------------------------------------------
async function initDashboard() {
  setupSearch();
  setupRatingSubmission();

  await populateYears();

  // Load baseline charts
  renderChartB();
  renderTableC();
  renderChartE();
  renderChartF();
  renderChartG();

  // Load Toy Story (#1) as the default showcase movie
  loadMovie(1);
}

document.addEventListener('DOMContentLoaded', initDashboard);
