function renderChart(programs, data) {
		var left_width = 100;
		var width = 367;

		var chart = d3.select(".main").append("svg")
			.attr("class", "chart")
			.attr("width", width)
			.attr("height", 140);

		var x = d3.scale.linear()
			.domain([0, d3.max(data)])
			.range([0, width - left_width]);

		var y = d3.scale.ordinal()
			.domain(data)
			.rangeBands([0, 120]);

		chart.selectAll("rect")
			.data(data)
		  .enter().append("rect")
			.attr("y", y)
			.attr("x", left_width)
			.attr("width", x)
			.attr("height", y.rangeBand());

		chart.selectAll("text")
			.data(data)
		  .enter().append("text")
			.attr("x", function(d) { return x(d) + left_width; })
			.attr("y", function(d) { return y(d) + y.rangeBand() / 2; })
			.attr("dx", -3) // padding-right
			.attr("dy", ".35em") // vertical-align: middle
			.attr("text-anchor", "end") // text-align: right
			.text(String);

		chart.selectAll("text.name")
			.data(programs)
		  .enter().append("text")
		  	.attr("x", left_width / 2)
		  	.attr("y", function(d){ return y(d) + y.rangeBand()/2; } )
		  	.attr("dy", ".36em")
		  	.attr("text-anchor", "middle")
		  	.attr('class', 'name')
		  	.text(String);
	}