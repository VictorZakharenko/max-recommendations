// Load the Visualization API and the controls package.
google.charts.load('current', {'packages':['corechart', 'controls']});

function drawTimeSeriesChart(timeSeriesData){
  // data prepare Sting dates to new Date obj
  timeSeriesData.data.forEach((item, i) => {
    item[0] = new Date(item[0]);
  });
  var data = new google.visualization.DataTable();
  data.addColumn('date', 'Date'); // Implicit domain label col.
  data.addColumn('number', 'Кол-во целей выполненных подписчиками');
  data.addColumn('number', 'Кол-во целей выполненных после прямого перехода из email');
  data.addColumn({'type': 'string', 'role': 'style' , 'opt_label':'send_on'});
  data.addColumn({'type': 'string', 'role': 'tooltip'});

  data.addRows(timeSeriesData.data);
  // Create a dashboard.
  var dashboard = new google.visualization.Dashboard(
      document.getElementById('dashboard_div'));

      /*  define the series object
       *  follows the standard 'series' option parameters, except it has two additonal parameters:
       *    hidden: true if the column is currently hidden
       *    altColor: changes the color of the legend entry (used to grey out hidden entries)
       */
      var series = {
          0: {
              hidden: false,
              visibleInLegend: true,
              color: '#e2431e'
          },
          0: {
              hidden: false,
              visibleInLegend: true,
              color: '#6f9654'
          },
      };


  var options = {
    series : series,
    title: 'Email эффект',
    hAxis: { title: 'Дата' },
    vAxis: { title: 'Количество целей' },
    legend: { position: 'top' , maxLines: 2},
    pointSize: 0.1,
    tooltip: { trigger: 'selection' },
    chartArea:{left:'7%',top:40,width:'80%',height:'80%'},
    height: 500,
  }



  var chart = new google.visualization.ChartWrapper({
    'chartType': 'LineChart',
    'containerId': 'curve_chart',
    'options': options
  });

  var goalsTypeCategory = new google.visualization.ControlWrapper({
    'controlType': 'ChartRangeFilter',
    'containerId': 'filter_div',

  });

  goalsTypeCategory.setOptions({'width': '100%','height': '50','filterColumnLabel': 'Date'})
  dashboard.bind(goalsTypeCategory,chart);
  // Draw the dashboard.
  dashboard.draw(data);

}

function drawChart(goals_no_email_count, goals_associate_with_email_count, goals_from_email_count) {

  //диаграмма
  var data_diag = google.visualization.arrayToDataTable([
    ['Источник', 'Количество выполненных целей'],
    ['Целей выполнено - email неизвестен',     parseInt(goals_no_email_count)],
    ['Целей выполнено - ассоциировано с email',      parseInt(goals_associate_with_email_count)],
    ['Целей выполнено - прямой переход из письма',      parseInt(goals_from_email_count)],
  ]);

  var options_diag = {
    title: 'Доля целей с известным, неизвестным email и целей выполненных после прямого перехода из email',
    is3D: true,
  };

  var chart_diag = new google.visualization.PieChart(document.getElementById('piechart_3d'));
  chart_diag.draw(data_diag, options_diag);

}
