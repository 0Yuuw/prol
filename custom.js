Sao.config.title = 'ProLibre';
Sao.config.icon_colors = '#823126,#3e4950,#e78e42'.split(',');

Sao.common.timedelta.parse = function(text, converter) {
    if (!text) {
        return null;
    }
    if (!converter) {
        converter = Sao.common.timedelta.DEFAULT_CONVERTER;
    }
    var separators = Sao.common.timedelta._get_separator();
    var separator;
    for (var k in separators) {
        separator = separators[k];
        text = text.replace(separator, separator + ' ');
    }

    var seconds = 0;
    var sec;
    var parts = text.split(' ');
    for (var i = 0; i < parts.length; i++) {
        var part = parts[i];
        if (part.contains(':')) {
            var subparts = part.split(':');
            var subconverter = [
                converter.h, converter.m, converter.s];
            for (var j = 0;
                    j < Math.min(subparts.length, subconverter.length);
                    j ++) {
                var t = subparts[j];
                var v = subconverter[j];
                sec = Math.abs(parseFloat(t)) * v;
                if (!isNaN(sec)) {
                    seconds += sec;
                }
            }
        } else {
            var found = false;
            for (var key in separators) {
                separator =separators[key];
                if (part.endsWith(separator)) {
                    part = part.slice(0, -separator.length);
                    sec = Math.abs(parseFloat(part)) * converter[key];
                    if (!isNaN(sec)) {
                        seconds += sec;
                    }
                    found = true;
                    break;
                }
            }
            if (!found) {
                sec = Math.abs(parseFloat(part));
                if (!isNaN(sec)) {
                    seconds += sec*60;
                }
            }
        }
    }
    if (text.contains('-')) {
        seconds *= -1;
    }
    return Sao.TimeDelta(null, seconds);
};
