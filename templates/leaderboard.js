var data = [
{% for user in scores.keys() %}
  ["{{user}}" {% for score in scores[user] %} , "{{score}}" {% endfor %} ],
{% endfor %}
];
