$(document).ready(function () {

        function exportTableToCSV($table, filename) {

        var $rows = $table.find('tr:has(td),tr:has(th)'),

            // Temporary delimiter characters unlikely to be typed by keyboard
            // This is to avoid accidentally splitting the actual contents
            tmpColDelim = String.fromCharCode(11), // vertical tab character
            tmpRowDelim = String.fromCharCode(0), // null character

            // actual delimiter characters for CSV format
            colDelim = '","',
            rowDelim = '"\r\n"',

            // Grab text from table into CSV formatted string
            csv = '"' + $rows.map(function (i, row) {
                var $row = $(row), $cols = $row.find('td,th');

                return $cols.map(function (j, col) {
                    //var $col = $(col), text = $col.text();
                    var $col = $(col), html = $col.html(), text = $col.text() ;

                    // if the cell has any super- or sub- script remove it
                    // because it's purely a visual helper
                    if(html.match('(sub|sup)') != null)
                    {
                        text = html.replace(/<.*(sub|sup).*\/(sub|sup).*>/g,'') ;
                    }

                    return text.replace(/"/g, '""'); // escape double quotes

                }).get().join(tmpColDelim);

            }).get().join(tmpRowDelim)
                .split(tmpRowDelim).join(rowDelim)
                .split(tmpColDelim).join(colDelim) + '"',



            // Data URI
            csvData = 'data:application/csv;charset=utf-8,' + encodeURIComponent(csv);

                if (window.navigator.msSaveBlob) { // IE 10+
                        //alert('IE' + csv);
                        window.navigator.msSaveOrOpenBlob(new Blob([csv], {type: "text/plain;charset=utf-8;"}), filename)
                }
                else {
                        $(this).attr({ 'download': filename, 'href': csvData, 'target': '_blank' });
                }
    }

    // This must be a hyperlink
    $("#xx").on('click', function (event) {

        exportTableToCSV.apply(this, [$('#downloadabletable'), 'export.csv']);

        // IF CSV, don't do event.preventDefault() or return false
        // We actually need this to be a typical hyperlink
    });

});

var getCellValue = function(tr, idx){
    var text = tr.children[idx].innerText || tr.children[idx].textContent;
    var numMatch = text.match(/^\${0,1}-{0,1}[0-9\.,]+$/);

    // if it's a number, convert it
    return (numMatch == null ? text : Number(text.replace(/[^0-9\.-]+/g,"")) ) ;
} ;

var comparer = function(idx, asc) { return function(a, b) { return function(v1, v2) {
        return v1 !== '' && v2 !== '' && !isNaN(v1) && !isNaN(v2) ? v1 - v2 : v1.toString().localeCompare(v2);
    }(getCellValue(asc ? a : b, idx), getCellValue(asc ? b : a, idx));
}};

// do the work...
Array.prototype.slice.call(document.querySelectorAll('th')).forEach(function(th) { th.addEventListener('click', function() {
        var table = th.parentNode
        while(table.tagName.toUpperCase() != 'TABLE') table = table.parentNode;
        Array.prototype.slice.call(table.querySelectorAll('tr:nth-child(n+2)'))
            .sort(comparer(Array.prototype.slice.call(th.parentNode.children).indexOf(th), this.asc = !this.asc))
            .forEach(function(tr) { table.appendChild(tr) });
    })
});
