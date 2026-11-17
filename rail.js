(() => {
    const mapStatus = document.getElementById('map-status');
    const rows = document.getElementById('unemployment-rows');

    if (typeof railData === 'undefined') {
        mapStatus.textContent = 'Les données de la ligne n’ont pas pu être chargées.';
        rows.firstElementChild.firstElementChild.textContent = 'Les données de chômage n’ont pas pu être chargées.';
        return;
    }

    const communes = [
        ['30007', 'Alès', 'Alès'],
        ['30305', 'Salindres', 'Salindres'],
        ['30271', 'Saint-Julien-de-Cassagnas', 'Saint-Julien - les Fumades'],
        ['30227', 'Saint-Ambroix', 'Saint-Ambroix'],
        ['30171', 'Molières-sur-Cèze', 'Molières-sur-Cèze et Gammal'],
        ['30216', 'Robiac-Rochessadoule', 'Robiac'],
        ['30037', 'Bessèges', 'Bessèges']
    ];
    const years = ['2013', '2015', '2020', '2023'];
    const formatter = new Intl.NumberFormat('fr-FR', { minimumFractionDigits: 1, maximumFractionDigits: 1 });
    rows.replaceChildren();
    for (const [code, name, stationNames] of communes) {
        const row = document.createElement('tr');
        const heading = document.createElement('th');
        heading.scope = 'row';
        heading.textContent = name;
        const detail = document.createElement('span');
        detail.className = 'station-detail';
        detail.textContent = `Gare : ${stationNames}`;
        heading.append(detail);
        row.append(heading);
        for (const year of years) {
            const cell = document.createElement('td');
            const rate = railData.rates[code]?.[year];
            cell.textContent = typeof rate === 'number' ? `${formatter.format(rate)} %` : 'Non disponible';
            row.append(cell);
        }
        rows.append(row);
    }

    if (typeof L === 'undefined') {
        mapStatus.textContent = 'La carte n’a pas pu être chargée. Vérifiez votre connexion Internet.';
        return;
    }

    const map = L.map('rail-map', { scrollWheelZoom: false });
    const tiles = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">contributeurs OpenStreetMap</a>'
    }).addTo(map);
    tiles.on('tileerror', () => {
        mapStatus.textContent = 'Le fond de carte OpenStreetMap n’a pas pu être chargé. Vérifiez votre connexion Internet.';
        mapStatus.hidden = false;
    });
    const line = L.polyline(railData.route, { color: '#b54d30', weight: 5, opacity: 0.9 }).addTo(map);
    for (const station of railData.stations) {
        L.marker(station.position, { title: station.name, alt: `Gare de ${station.name}` })
            .addTo(map)
            .bindPopup(document.createTextNode(station.name));
    }
    map.fitBounds(line.getBounds(), { padding: [30, 30] });
    mapStatus.hidden = true;
})();
