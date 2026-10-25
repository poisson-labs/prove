// poisson-prove: the static dashboard's one script. It sorts a table by the column whose
// header is clicked and filters a table's rows by typed text; nothing else. Every page works
// with it off, and it loads nothing.
(function () {
  "use strict";
  function sortable(table) {
    var headers = table.querySelectorAll("thead th");
    Array.prototype.forEach.call(headers, function (th, index) {
      th.addEventListener("click", function () {
        var body = table.tBodies[0];
        var rows = Array.prototype.slice.call(body.rows);
        var ascending = th.getAttribute("data-asc") !== "1";
        Array.prototype.forEach.call(headers, function (other) { other.removeAttribute("data-asc"); });
        th.setAttribute("data-asc", ascending ? "1" : "0");
        rows.sort(function (x, y) {
          var a = key(x.cells[index]), b = key(y.cells[index]);
          var na = parseFloat(a), nb = parseFloat(b);
          var r = (!isNaN(na) && !isNaN(nb)) ? na - nb : a.localeCompare(b);
          return ascending ? r : -r;
        });
        rows.forEach(function (row) { body.appendChild(row); });
      });
    });
  }
  function key(cell) {
    if (!cell) { return ""; }
    var fact = cell.querySelector("[data-value]");
    var raw = cell.getAttribute("data-value") || (fact && fact.getAttribute("data-value"));
    if (raw) {
      try { var parsed = JSON.parse(raw); if (parsed !== null && typeof parsed !== "object") { return String(parsed); } } catch (e) { }
    }
    return cell.textContent.trim();
  }
  function filterable(input) {
    var table = document.getElementById(input.getAttribute("data-filter"));
    if (!table) { return; }
    input.hidden = false;
    input.addEventListener("input", function () {
      var wanted = input.value.toLowerCase();
      Array.prototype.forEach.call(table.tBodies[0].rows, function (row) {
        row.hidden = wanted !== "" && row.textContent.toLowerCase().indexOf(wanted) < 0;
      });
    });
  }
  Array.prototype.forEach.call(document.querySelectorAll("table[data-sort]"), sortable);
  Array.prototype.forEach.call(document.querySelectorAll("input[data-filter]"), filterable);
})();
