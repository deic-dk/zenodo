define(function(require, exports, module) {
  'use strict';

  var $ = require('jquery');
  var chooserDialog;

  function initUI(config){
    init_chooserButton(config);
    init_removeObjectButtons(config);
    init_createVersionButton(config);
    $('[data-toggle="tooltip"]').tooltip();
    $('i.error').tooltip({
      trigger: 'hover',
      animation: true,
      placement: 'top',
    });
  };

  return function(config) {
    initUI(config);
  };

function fixSlashes(str) {
    if(str.substr(-1)=='/') {
        var str = str.substr(0, str.length - 1);
    }
    if(str.substr(1)!='/') {
        var str = '/'+str;
    }
    return str;
}

function addScienceDataObject(config, path, name, kind, group){
    $.ajax({
        url: config.add_sciencedata_object_url,
        type: 'GET',
        data: {path: path, name: name, kind: kind, group: group}
    })
    .done(function(data) {
      //$(config.sciencedata_deposits).html(data);
      $(config.sciencedata_view).html(data);
      initUI(config);
      var text = $("button[name='create-version'] ").text()
      $("button[name='create-version']").html('<i class="fa fa-sciencedata"></i><span class="sd_button">'+text+'</span>');
    });
}

function stopSDSpin(){
  $("button[name='browse-sciencedata'] i.fa-sciencedata").removeClass('fa-spin');
}

function startSDSpin(){
  $("button[name='browse-sciencedata'] i.fa-sciencedata").addClass('fa-spin');
}

function createBrowser(chooseAction, config) {
    var buttons = {};
    buttons[ "Choose"] = function(ev) {
        var chosenFileOrFolder = fixSlashes($('#sciencedata_browser_div .chosen').attr('rel'));
        var chosenKind = $('#sciencedata_browser_div .chosen').attr('rel').endsWith('/')?'dir':'file';
        var chosenName = $('#sciencedata_object_name').val();
        var chosenGroup = $('select#group_folder').val();
        chooseAction(config, chosenFileOrFolder, chosenName, chosenKind, chosenGroup);
        stopSDSpin();
        chooserDialog.dialog("close");
    };
    buttons["Cancel"] = function(ev) {
      stopSDSpin();
      chooserDialog.dialog("close");
    };
    var dia = $("div#sciencedata_browser_div").dialog({//create dialog, but keep it closed
        title: "Choose file or folder to preserve",
        dialogClass: "ScienceData",
        autoOpen: false,
        height: 440,
        width: 620,
        modal: true,
        buttons: buttons
    });
    dia.hide();
    $('.ui-dialog-buttonpane button.ui-button, select#group_folder').addClass('btn');
    return dia;
}

function loadFileTree(config){
  var sciencedataIcon =  $("button[name='browse-sciencedata'] i.fa-sciencedata");
  $('button[title="close"]').click(function(ev){$("button[name='browse-sciencedata'] i.fa-sciencedata").removeClass('fa-spin');})
  startSDSpin();
  var group = $('#group_folder').val();
  $("#sciencedata_browser_div").fileTree({
    //root: '/',
    script: '/account/settings/sciencedata/sciencedata_proxy/apps/chooser/jqueryFileTree.php',
    multiFolder: false,
    selectFile: true,
    selectFolder: true,
    folder: '/',
    file: '',
    group: group
  },
  // single-click
  function(file) {
      $('#sciencedata_object_name').val(file.replace(/\/$/,"").split('/').reverse()[0]);
  },
  // double-click
  function(file) {
      var kind = $('#sciencedata_browser_div .chosen').attr('rel').endsWith('/')?'dir':'file';
      var name = $('#sciencedata_object_name').val();
      var group = $('select#group_folder').val();
      addScienceDataObject(config, file, name, kind, group);
      stopSDSpin();
      chooserDialog.dialog("close");
  });
}

function init_createVersionButton(config){
  var createVersionButton = $(config.create_version_button);
  var text = createVersionButton.text();
  createVersionButton.html('<i class="fa fa-sciencedata"></i><span class="sd_button">'+text+'</span>');
  createVersionButton.on('click', function(ev) {
    startSDSpin();
    $.ajax({
      url: config.create_version_url,
      type: 'GET'
    })
    .done(function(data) {
      stopSDSpin();
      location.reload();
    });
  });
}

function init_removeObjectButtons(config){
 $('.release').each(function(el){
    var removeObjectButton = $(this).find(config.remove_object_button).first();
    var sciencedata_object_id = $(this).attr('id');
    removeObjectButton.on('click', function(ev) {
      if(confirm("This will remove the connection of this deposit to ScienceData. New versions of the ScienceData object will have to be published manually or with a new DOI.")){
        $.ajax({
          url: config.remove_object_url,
          data: {sciencedata_object_id: sciencedata_object_id},
          type: 'GET'
        })
        .done(function(data) {
          location.reload();
        });
      }
    });
 });
}

function init_chooserButton(config){
  // ScienceData is the class name of the chooser dialog
  // If config.create_version_button is set, we're in the view.html template
    if($('.ScienceData').length || config.create_version_button){
        return;
    }
    var chooserButton = $(config.sciencedata_button);
    chooserButton.after('<div id="sciencedata_browser_div"></div>');
    var text = chooserButton.text()
    chooserButton.html('<i class="fa fa-sciencedata"></i><span class="sd_button">'+text+'</span>');
    chooserDialog = createBrowser(addScienceDataObject, config);
    $('.ui-dialog-titlebar').after('<div><span>Name: </span><input id="sciencedata_object_name" value=""></div>');
    $('#sciencedata_object_name').after($('#group_folder'));
    $('#group_folder').show();
    chooserButton.on('click', function(ev) {
        chooserDialog.show();
        chooserDialog.dialog('open');
        loadFileTree(config);
    });
    $('#group_folder').on('change', function(ev) {
     loadFileTree(config);
    });
}

});
